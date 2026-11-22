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


def untracked_summary(row: Dict[str, Any]) -> bool:
    """旧摘要缺少逐句人物标记，不能作为自动注入的来源。"""
    meta = row.get("metadata") or {}
    if meta.get("source_type") != "chat_summary" and not any(
        str(source or "").startswith("chat_summary:") for source in (meta.get("source"), row.get("source"))
    ):
        return False
    attribution = meta.get("attribution_fact_people")
    texts = facts(row)
    return not (
        meta.get("dedup_managed")
        and meta.get("evidence_message_ids")
        and texts
        and isinstance(attribution, dict)
        and all(attribution.get(text) == [] for text in texts)
    )


def expected_statement(fact: str, name: str, *, target_bound: bool = False) -> str:
    # 只自动核验单句、逐字对应的第一人称陈述。转述、引文和模型改写保留待核验。
    text = fact.strip().rstrip("。.!！")
    prefixes = (name, "我", "他", "她") if target_bound else (name, "我")
    for prefix in prefixes:
        if prefix and text.startswith(prefix):
            text = text[len(prefix) :]
            break
    if text.endswith(("吗", "么", "吧", "呢")):
        return ""
    if re.fullmatch(r"(?:喜欢|不喜欢|爱吃|不吃|住在|来自|擅长|是|每周)[\w\u3400-\u9fff]{1,32}", text):
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
    statement = expected_statement(fact, name, target_bound=meta.get("writeback_source") == "memory_flow_service")
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


def candidate_has_sender(metadata: Dict[str, Any], pid: str) -> bool:
    """保留候选前确认来源消息存在于同一聊天流，且全部来自目标账号。"""
    from sqlmodel import select

    from src.common.database.database import get_db_session
    from src.common.database.database_model import Messages
    from src.person_info.identity import person_id_for, resolve_user_id

    ids = metadata.get("evidence_message_ids")
    if not isinstance(ids, list) or not 0 < len(ids) <= 256 or not all(isinstance(i, str) and i for i in ids):
        return False
    if not metadata.get("chat_id") or not metadata.get("platform"):
        return False
    ids = set(ids)
    with get_db_session(auto_commit=False) as session:
        rows = session.exec(
            select(Messages.message_id, Messages.user_id)
            .where(
                Messages.session_id == metadata["chat_id"],
                Messages.platform == metadata["platform"],
                Messages.message_id.in_(ids),
            )
            .limit(len(ids) + 1)
        ).all()
    return (
        len(rows) == len(ids)
        and {row[0] for row in rows} == ids
        and all(
            person_id_for(metadata["platform"], resolve_user_id(metadata["platform"], user)) == pid
            for user in {row[1] for row in rows}
        )
    )


class PersonVerificationMixin:
    def hold_writeback_candidate(self, candidate_id: str, person_id: str, kwargs: Dict[str, Any]) -> None:
        with self.transaction(immediate=True) as conn:
            conn.execute(
                "INSERT INTO person_writeback_candidates VALUES(?,?,?,unixepoch()+3600) ON CONFLICT(id) DO NOTHING",
                (candidate_id, person_id, json.dumps(kwargs, ensure_ascii=False)),
            )

    def take_due_writeback_candidate(self) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT id,payload FROM person_writeback_candidates WHERE retry_at<=unixepoch() ORDER BY retry_at LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        with self.transaction(immediate=True) as conn:
            claimed = conn.execute(
                "UPDATE person_writeback_candidates SET retry_at=unixepoch()+3600 WHERE id=? AND retry_at<=unixepoch()",
                (row[0],),
            ).rowcount
            if not claimed:
                return None
        return json.loads(row[1])

    def finish_writeback_candidate(self, candidate_id: str) -> None:
        if self._conn.execute("SELECT 1 FROM person_writeback_candidates WHERE id=?", (candidate_id,)).fetchone():
            with self.transaction(immediate=True) as conn:
                conn.execute("DELETE FROM person_writeback_candidates WHERE id=?", (candidate_id,))

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
                    was_verified=CASE WHEN revision<>excluded.revision THEN 0 ELSE was_verified END,
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
        for pid, fact, old_state, proof, supplement in self._conn.execute(
            "SELECT person_id,fact,state,proof,supplement FROM person_fact_verification "
            "WHERE paragraph_hash=? AND revision=? AND (state='verified' OR was_verified=1)",
            (row["hash"], rev),
        ).fetchall():
            if person_id and pid != person_id:
                continue
            state, latest = inspect_source(row, pid, fact, supplement)
            if (state, latest) != (old_state, proof):
                with self.transaction(immediate=True) as conn:
                    updated = conn.execute(
                        "UPDATE person_fact_verification SET state=?,proof=?,was_verified=1,retry_at=unixepoch()+3600 "
                        "WHERE paragraph_hash=? AND person_id=? AND fact=? AND revision=? AND state=? AND proof=? "
                        "AND supplement=?",
                        (state, latest, row["hash"], pid, fact, rev, old_state, proof, supplement),
                    ).rowcount
                if not updated:
                    continue
            if state == "verified":
                verified.add(fact)
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
                "UPDATE person_fact_verification SET state='pending', priority=1, proof='', was_verified=0, supplement=? "
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

    def recover_observed_names(self, limit: int, group_id: Optional[str] = None) -> bool:
        """群内查询仅追赶该群的消息，全局游标已处理的部分可以跳过。"""
        from sqlmodel import select

        from src.common.database.database import get_db_session
        from src.common.database.database_model import Messages
        from src.A_memorix.core.utils.summary_identity import observe_identity

        progress = self._conn.execute("SELECT last_message FROM observed_names_cursor WHERE id=1").fetchone()
        last = progress[0] if progress else 0
        query = select(
            Messages.id,
            Messages.platform,
            Messages.user_id,
            Messages.group_id,
            Messages.user_nickname,
            Messages.user_cardname,
        )
        if group_id is not None:
            scoped = self._conn.execute(
                "SELECT last_message,pending FROM observed_group_cursor WHERE group_id=?", (group_id,)
            ).fetchone()
            last = max(last, scoped[0] if scoped else 0)
            query = query.where(Messages.group_id == group_id)
        with get_db_session(auto_commit=False) as session:
            rows = session.exec(query.where(Messages.id > last).order_by(Messages.id).limit(limit + 1)).all()
        ready = len(rows) <= limit
        batch = rows[:limit]
        if batch:
            last = batch[-1][0]
        for platform, user, group, nickname, card in dict.fromkeys(tuple(row[1:]) for row in batch):
            if platform and user:
                observe_identity(
                    self, platform=platform, user_id=user, group_id=group or "", aliases=[nickname or "", card or ""]
                )
        if group_id is not None and batch:
            with self.transaction(immediate=True) as conn:
                conn.execute(
                    "INSERT INTO observed_group_cursor VALUES(?,?,?) ON CONFLICT(group_id) DO UPDATE SET "
                    "last_message=excluded.last_message,pending=excluded.pending "
                    "WHERE last_message<=excluded.last_message",
                    (group_id, last, int(not ready)),
                )
        elif group_id is not None and scoped and scoped[1]:
            with self.transaction(immediate=True) as conn:
                conn.execute(
                    "UPDATE observed_group_cursor SET pending=0 WHERE group_id=? AND last_message<=? AND pending=1",
                    (group_id, last),
                )
        elif group_id is None and batch:
            with self.transaction(immediate=True) as conn:
                conn.execute(
                    "INSERT INTO observed_names_cursor VALUES(1,?) ON CONFLICT(id) DO UPDATE SET "
                    "last_message=MAX(last_message,excluded.last_message)",
                    (last,),
                )
        return ready

    def recover_active_group_names(self, limit: int) -> None:
        group = self._conn.execute(
            "SELECT group_id FROM observed_group_cursor WHERE pending=1 ORDER BY last_message LIMIT 1"
        ).fetchone()
        if group:
            self.recover_observed_names(limit, group[0])

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
        retries = conn.execute(
            "SELECT paragraph_hash,person_id,fact,revision,supplement,state FROM person_fact_verification "
            "WHERE state IN ('insufficient','conflict') AND retry_at<=unixepoch() ORDER BY retry_at LIMIT 1"
        ).fetchall()
        for task in tasks:
            self._verify_task(*task)
        for task in retries:
            self._verify_task(*task)
        return len(tasks) + len(retries)

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

    def _verify_task(
        self, key: str, pid: str, fact: str, rev: str, supplement: str, old_state: str = "pending"
    ) -> None:
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
                    "UPDATE person_fact_verification SET state=?,proof=?,was_verified=MAX(was_verified,?),retry_at=unixepoch()+3600 "
                    "WHERE paragraph_hash=? "
                    "AND person_id=? AND fact=? AND revision=? AND state=? AND supplement=?",
                    (state, proof, int(state == "verified"), key, pid, fact, rev, old_state, supplement),
                )
