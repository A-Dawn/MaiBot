"""按事实核验人物归属。原始段落只读；核验记录可独立清除并重新生成。"""

from hashlib import sha256
from typing import Any, Dict, List, Optional, Tuple

import json
import re


def bindings(row: Dict[str, Any]) -> List[str]:
    meta = row.get("metadata") or {}
    value = meta.get("person_ids")
    people = list(value) if isinstance(value, list) else [value] if isinstance(value, str) else []
    if meta.get("person_id"):
        people.append(meta["person_id"])
    identity_names = meta.get("identity_bindings")
    if isinstance(identity_names, dict):
        people.extend(item.get("person_id") for item in identity_names.values() if isinstance(item, dict))
    for source in (row.get("source"), meta.get("source")):
        if isinstance(source, str) and source.startswith("person_fact:"):
            people.append(source.removeprefix("person_fact:"))
    return list(dict.fromkeys(str(pid) for pid in people if pid))


def facts(row: Dict[str, Any]) -> List[str]:
    texts = (row.get("metadata") or {}).get("dedup_fact_texts")
    if texts is None:
        return [row["content"]]
    return [text for text in texts if isinstance(text, str) and text] if isinstance(texts, list) else []


def revision(row: Dict[str, Any]) -> str:
    payload = [1, row["content"], row["source"], row.get("is_deleted"), row["metadata"]]
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def expected_statement(fact: str, name: str) -> str:
    # 只自动核验单句、逐字对应的第一人称陈述。转述、引文和模型改写保留待核验。
    text = fact.strip().rstrip("。.!！")
    for prefix in (name, "我"):
        if prefix and text.startswith(prefix):
            text = text[len(prefix) :]
            break
    if re.fullmatch(r"(?:喜欢|不喜欢|爱吃|不吃|住在|来自|擅长)[\w\u3400-\u9fff]{1,32}", text):
        return "我" + text
    return ""


def inspect_source(row: Dict[str, Any], pid: str, fact: str, supplement: str = "[]") -> Tuple[str, str]:
    from sqlalchemy import case, func
    from sqlmodel import select

    from src.common.database.database import get_db_session
    from src.common.database.database_model import Individual, Messages, PersonInfo
    from src.common.utils.utils_message import MessageUtils
    from src.common.data_models.message_component_data_model import TextComponent
    from src.person_info.identity import person_id_for, resolve_user_id

    meta = row["metadata"] or {}
    ids = json.loads(supplement) or meta.get("evidence_message_ids") or []
    chat = meta.get("chat_id")
    name = str(meta.get("person_name") or "")
    declared = meta.get("identity_bindings")
    for canonical, binding in declared.items() if isinstance(declared, dict) else ():
        if isinstance(binding, dict) and binding.get("person_id") == pid:
            name = canonical
            break
    statement = expected_statement(fact, name)
    if (
        not statement
        or not chat
        or not isinstance(ids, list)
        or not ids
        or len(ids) > 256
        or not all(isinstance(i, str) and i for i in ids)
    ):
        return "insufficient", ""
    with get_db_session(auto_commit=False) as session:
        body = case((func.length(Messages.raw_content) <= 16384, Messages.raw_content), else_=None).label("body")
        query = select(
            Messages.message_id,
            Messages.platform,
            Messages.user_id,
            Messages.user_nickname,
            Messages.user_cardname,
            body,
        ).where(Messages.session_id == chat, Messages.message_id.in_(ids))
        if meta.get("platform"):
            query = query.where(Messages.platform == meta["platform"])
        messages = session.exec(query.limit(len(set(ids)) + 1)).all()
        named = bool(name and fact.startswith(name))
        display_name = (
            session.exec(select(Individual.display_name).join(PersonInfo).where(PersonInfo.person_id == pid)).first()
            if named
            else None
        )
        seen = set()
        matches = []
        for msg in messages:
            if msg.message_id in seen:
                return "conflict", "duplicate_message_id"
            seen.add(msg.message_id)
            if msg.body is None:
                return "insufficient", "oversized_message"
            try:
                components = MessageUtils.from_db_record_msg_to_MaiSeq(msg.body).components
            except (ValueError, TypeError, KeyError, IndexError, NotImplementedError):
                return "insufficient", "invalid_message_content"
            if len(components) != 1 or not isinstance(components[0], TextComponent):
                continue
            if components[0].text.strip().rstrip("。.!！") == statement:
                author = person_id_for(msg.platform, resolve_user_id(msg.platform, msg.user_id))
                if (
                    named
                    and author == pid
                    and name.removesuffix(f" [{pid}]")
                    not in {
                        msg.user_nickname,
                        msg.user_cardname,
                        msg.user_id,
                        display_name,
                    }
                ):
                    return "insufficient", "unconfirmed_subject_name"
                matches.append((author, msg.message_id, msg.platform, msg.user_id))
    if len(seen) != len(set(ids)):
        return "insufficient", "missing_message"
    if not matches:
        return "insufficient", ""
    proof = json.dumps(sorted(matches), ensure_ascii=False)
    if {item[0] for item in matches} != {pid}:
        return "conflict", proof
    return "verified", proof


class PersonVerificationMixin:
    def _request_verification(self, row: Dict[str, Any], priority: int) -> None:
        people = bindings(row)
        if not people or row.get("is_deleted"):
            return
        rev = revision(row)
        explicit = row["metadata"].get("attribution_fact_people", {})
        if not isinstance(explicit, dict):
            return
        tasks = []
        texts = facts(row)
        if len(texts) > 64:
            return
        for fact in texts:
            candidates = explicit.get(fact, people)
            if isinstance(candidates, list) and len(candidates) == 1 and candidates[0] in people:
                tasks.append((row["hash"], candidates[0], fact, rev, priority))
        if not tasks:
            return
        existing = {
            (r[0], r[1]): (r[2], r[3], r[4])
            for r in self._conn.execute(
                "SELECT person_id,fact,revision,state,priority FROM person_fact_verification WHERE paragraph_hash=?",
                (row["hash"],),
            )
        }
        changed = [
            t
            for t in tasks
            if (old := existing.get((t[1], t[2]))) is None or old[0] != rev or old[1] == "pending" and old[2] < priority
        ]
        if changed:
            with self.transaction(immediate=True) as conn:
                current = self.get_paragraph(row["hash"])
                if not current or revision(current) != rev:
                    return
                conn.executemany(
                    """
                    INSERT INTO person_fact_verification(paragraph_hash,person_id,fact,revision,priority,state)
                    VALUES(?,?,?,?,?,'pending') ON CONFLICT(paragraph_hash,person_id,fact) DO UPDATE SET
                    state=CASE WHEN revision<>excluded.revision THEN 'pending' ELSE state END,
                    supplement=CASE WHEN revision<>excluded.revision THEN '[]' ELSE supplement END,
                    proof=CASE WHEN revision<>excluded.revision THEN '' ELSE proof END,
                    priority=MAX(priority,excluded.priority), revision=excluded.revision
                """,
                    changed,
                )

    def verified_facts(self, row: Dict[str, Any], person_id: Optional[str] = None) -> List[str]:
        self._request_verification(row, 1)
        rev = revision(row)
        verified = set()
        for pid, fact, proof, supplement in self._conn.execute(
            "SELECT person_id,fact,proof,supplement FROM person_fact_verification "
            "WHERE paragraph_hash=? AND revision=? AND state='verified'",
            (row["hash"], rev),
        ).fetchall():
            if person_id and pid != person_id:
                continue
            # 账号合并或源消息修改后，旧证明立即停止生效。
            state, latest = inspect_source(row, pid, fact, supplement)
            if state == "verified" and latest == proof:
                verified.add(fact)
            else:
                with self.transaction(immediate=True) as conn:
                    conn.execute(
                        "UPDATE person_fact_verification SET state='pending',priority=1 "
                        "WHERE paragraph_hash=? AND person_id=? AND fact=? AND revision=? AND proof=? AND supplement=?",
                        (row["hash"], pid, fact, rev, proof, supplement),
                    )
        return [text for text in facts(row) if text in verified]

    def review_attribution(
        self,
        *,
        paragraph_hash: str,
        person_id: str,
        fact: str,
        expected_revision: str,
        previous_message_ids: List[str],
        message_ids: List[str],
    ) -> None:
        """管理端可补充同一聊天流的来源，清空列表即可撤回补充。核验规则与自动任务一致。"""
        if (
            not isinstance(message_ids, list)
            or len(message_ids) > 256
            or not all(isinstance(item, str) and item.strip() for item in message_ids)
        ):
            raise ValueError("证据必须是至多 256 个消息 ID")
        with self.transaction(immediate=True) as conn:
            row = self.get_paragraph(paragraph_hash)
            if not row or row.get("is_deleted") or revision(row) != expected_revision:
                raise ValueError("段落已变更，请重新读取")
            changed = conn.execute(
                "UPDATE person_fact_verification SET state='pending', priority=1, proof='', supplement=? "
                "WHERE paragraph_hash=? AND person_id=? AND fact=? AND revision=? AND supplement=?",
                (
                    json.dumps(sorted(set(message_ids))),
                    paragraph_hash,
                    person_id,
                    fact,
                    expected_revision,
                    json.dumps(sorted(set(previous_message_ids))),
                ),
            ).rowcount
            if changed != 1:
                raise ValueError("核验记录已变更或不存在")

    def recover_observed_names(self, limit: int) -> None:
        from sqlmodel import select

        from src.common.database.database import get_db_session
        from src.common.database.database_model import Messages
        from src.A_memorix.core.utils.summary_identity import observe_identity

        cursor = self._conn.execute("SELECT last_message FROM observed_names_cursor WHERE id=1").fetchone()
        with get_db_session(auto_commit=False) as session:
            rows = session.exec(
                select(
                    Messages.id,
                    Messages.platform,
                    Messages.user_id,
                    Messages.group_id,
                    Messages.user_nickname,
                    Messages.user_cardname,
                )
                .where(Messages.id > (cursor[0] if cursor else 0))
                .order_by(Messages.id)
                .limit(limit)
            ).all()
        for _, platform, user, group, nickname, card in rows:
            if platform and user:
                observe_identity(
                    self, platform=platform, user_id=user, group_id=group or "", aliases=[nickname or "", card or ""]
                )
        if rows:
            with self.transaction(immediate=True) as conn:
                conn.execute(
                    "INSERT INTO observed_names_cursor VALUES(1,?) ON CONFLICT(id) DO UPDATE SET "
                    "last_message=MAX(last_message,excluded.last_message)",
                    (rows[-1][0],),
                )

    def verify_person_fact_batch(self, limit: int = 8) -> int:
        conn = self._conn
        cursor = conn.execute("SELECT last_row FROM person_verification_cursor WHERE id=1").fetchone()
        rows = conn.execute(
            "SELECT rowid,hash FROM paragraphs WHERE rowid>? ORDER BY rowid LIMIT ?",
            (cursor[0] if cursor else 0, limit),
        ).fetchall()
        for _, key in rows:
            row = self.get_paragraph(key)
            if row:
                self._request_verification(row, 0)
        if rows:
            with self.transaction(immediate=True) as conn:
                conn.execute(
                    "INSERT INTO person_verification_cursor VALUES(1,?) ON CONFLICT(id) "
                    "DO UPDATE SET last_row=MAX(last_row,excluded.last_row)",
                    (rows[-1][0],),
                )
        tasks = self._conn.execute(
            "SELECT paragraph_hash,person_id,fact,revision,supplement FROM person_fact_verification "
            "WHERE state='pending' ORDER BY priority DESC,rowid LIMIT ?",
            (limit,),
        ).fetchall()
        for task in tasks:
            self._verify_task(*task)
        return len(tasks)

    def verify_written_fact(self, key: str, pid: str, fact: str) -> None:
        row = self.get_paragraph(key)
        if row and not row.get("is_deleted"):
            self._request_verification(row, 1)
            pending = self._conn.execute(
                "SELECT revision,supplement FROM person_fact_verification WHERE paragraph_hash=? AND person_id=? "
                "AND fact=? AND state='pending'",
                (key, pid, fact),
            ).fetchone()
            if pending:
                self._verify_task(key, pid, fact, *pending)

    def _verify_task(self, key: str, pid: str, fact: str, rev: str, supplement: str) -> None:
        row = self.get_paragraph(key)
        if not row or row.get("is_deleted") or revision(row) != rev:
            with self.transaction(immediate=True) as conn:
                conn.execute(
                    "DELETE FROM person_fact_verification WHERE paragraph_hash=? AND person_id=? "
                    "AND fact=? AND revision=?",
                    (key, pid, fact, rev),
                )
            if row:
                self._request_verification(row, 0)
            return
        state, proof = inspect_source(row, pid, fact, supplement)
        with self.transaction(immediate=True) as conn:
            current = self.get_paragraph(key)
            if current and revision(current) == rev:
                conn.execute(
                    "UPDATE person_fact_verification SET state=?,proof=? WHERE paragraph_hash=? "
                    "AND person_id=? AND fact=? AND revision=? AND state='pending' AND supplement=?",
                    (state, proof, key, pid, fact, rev, supplement),
                )
