"""由平台用户 ID 驱动的稳定身份及历史称呼映射。"""

from typing import Any, Dict, List

import time


class MetadataIdentityMixin:
    def observe_person_identity(
        self,
        *,
        person_id: str,
        platform: str,
        user_id: str,
        aliases: List[str],
        group_id: str = "",
        preferred_name: str = "",
        include_history: bool = True,
        confirmed_sender: bool = True,
        previous_user_id: str = "",
    ) -> Dict[str, Any]:
        """只按 ID 合并身份，保留每次观察到的昵称，不用昵称认领其他用户。"""
        if not person_id or not platform.strip() or not user_id.strip():
            raise ValueError("身份映射必须包含 person_id、platform 和 user_id")
        names = list(dict.fromkeys(name.strip() for name in aliases if name.strip()))
        now = time.time()
        with self.transaction(immediate=True) as conn:
            existing = conn.execute(
                "SELECT platform, user_id, canonical_name FROM person_identities WHERE person_id = ?",
                (person_id,),
            ).fetchone()
            owner = conn.execute("SELECT person_id FROM person_identities WHERE platform=? AND user_id=?",
                                 (platform, user_id)).fetchone()
            conflicting_owner = owner is not None and owner[0] != person_id
            conflicting_header = existing is not None and (
                existing[0] != platform or existing[1] not in (user_id, previous_user_id)
            )
            if conflicting_owner or conflicting_header:
                # 保留有冲突的旧主键，当前消息仍使用根据平台账号计算出的 ID。
                previous = str(owner[0]) if conflicting_owner else str(existing[1])
                conn.execute("INSERT OR IGNORE INTO identity_binding_conflicts VALUES(?,?,?,?)",
                             (platform, user_id, person_id, previous))
                return {"person_id": person_id, "platform": platform, "user_id": user_id,
                        "canonical_name": f"{user_id} [{person_id}]", "aliases": names}
            if existing is not None:
                if existing[1] != user_id:
                    conn.execute("UPDATE person_identities SET user_id=? WHERE person_id=?", (user_id, person_id))
                    conn.execute("INSERT INTO identity_repair_log(kind,item,previous,updated) VALUES('account',?,?,?)",
                                 (person_id, previous_user_id, user_id))
                canonical_name = str(existing[2])
            else:
                canonical_name = preferred_name.strip() or next(iter(names), user_id)
                collision = conn.execute(
                    "SELECT person_id FROM person_identities WHERE canonical_name = ?",
                    (canonical_name,),
                ).fetchone()
                if collision is not None:
                    canonical_name = f"{canonical_name} [{person_id}]"
                conn.execute(
                    "INSERT INTO person_identities VALUES (?, ?, ?, ?, ?, ?)",
                    (person_id, platform, user_id, canonical_name, now, now),
                )
            conn.execute("UPDATE person_identities SET updated_at = ? WHERE person_id = ?", (now, person_id))
            for name in list(dict.fromkeys([canonical_name, *names])):
                conn.execute(
                    """INSERT INTO person_identity_aliases(person_id, alias, group_id, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(person_id, alias, group_id) DO UPDATE SET last_seen = excluded.last_seen""",
                    (person_id, name, group_id, now, now),
                )
            conn.executemany(
                "INSERT OR IGNORE INTO observed_person_names VALUES (?, ?, ?, ?)",
                [(platform, group_id, name, person_id) for name in names if confirmed_sender],
            )
        if not include_history:
            return {"person_id": person_id, "platform": platform, "user_id": user_id,
                    "canonical_name": canonical_name, "aliases": names}
        identity = self.get_person_identity(person_id)
        assert identity is not None
        return identity

    def bound_account(self, person_id: str) -> str:
        row = self._conn.execute("SELECT user_id FROM person_identities WHERE person_id=?", (person_id,)).fetchone()
        return row[0] if row else ""

    def observed_names_ready(self, latest_host_message: int) -> bool:
        target = self._conn.execute("SELECT last_message FROM observed_names_baseline WHERE id=1").fetchone()
        if target is None:
            with self.transaction(immediate=True) as conn:
                conn.execute("INSERT OR IGNORE INTO observed_names_baseline VALUES(1,?)", (latest_host_message,))
                target = conn.execute("SELECT last_message FROM observed_names_baseline WHERE id=1").fetchone()
        progress = self._conn.execute("SELECT last_message FROM observed_names_cursor WHERE id=1").fetchone()
        return target[0] <= (progress[0] if progress else 0)

    def observed_name_candidates(self, platform: str, group_id: str, name: str) -> List[str]:
        rows = self._conn.execute(
            "SELECT n.person_id, i.user_id FROM observed_person_names n JOIN person_identities i ON i.person_id=n.person_id "
            "WHERE n.platform=? AND n.group_id=? AND n.name=? AND i.platform=n.platform LIMIT 2",
            (platform, group_id, name),
        )
        from src.person_info.identity import person_id_for, resolve_user_id

        candidates = list(rows)
        if any(person_id_for(platform, resolve_user_id(platform, user)) != pid for pid, user in candidates):
            return [""]
        return [pid for pid, _ in candidates]

    def get_person_identity(self, person_id: str) -> Dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT person_id, platform, user_id, canonical_name FROM person_identities WHERE person_id = ?",
            (person_id,),
        ).fetchone()
        if row is None:
            return None
        aliases = self._conn.execute(
            "SELECT DISTINCT alias FROM person_identity_aliases WHERE person_id = ? ORDER BY alias",
            (person_id,),
        ).fetchall()
        return {
            "person_id": row[0],
            "platform": row[1],
            "user_id": row[2],
            "canonical_name": row[3],
            "aliases": [str(item[0]) for item in aliases],
        }

    def find_person_identities(self, alias: str, *, platform: str = "") -> List[Dict[str, Any]]:
        """同名称可以对应多人；调用方不得取第一条来猜测人物身份。"""
        rows = self._conn.execute(
            """SELECT DISTINCT i.person_id FROM person_identities i
               JOIN person_identity_aliases a ON a.person_id = i.person_id
               WHERE a.alias = ? AND (? = '' OR i.platform = ?) ORDER BY i.person_id""",
            (alias.strip(), platform, platform),
        ).fetchall()
        identities: List[Dict[str, Any]] = []
        for row in rows:
            identity = self.get_person_identity(str(row[0]))
            assert identity is not None
            identities.append(identity)
        return identities
