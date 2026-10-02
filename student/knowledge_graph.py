"""Knowledge Graph (Light Memory Version)
=================================
For managing students-Concept-questions-mastery Neo4j / SQLite / Figure database。

Core functions:
1. Concept/questions/Student registration
2. Titles and concepts(Polyweight)Association
3. Record answers Attempt and update mastery (Ownership p∈(0,1))
4. Index forgotten decline + Logistic Incremental Update + streak Adjust stability
5. Simple recommendations (see medium mastery or low coverage concepts)）
6. JSON Endurance (optional callable)）

Follow-up could be extended:
- Introduction BKT / Elo / Performance Factor Model
- Targeted Exercise Set dynamic difficulty
- Add Resource(Lesson)Overwrite Relationships
- Multi-student group statistics, conceptual consolidation/Split Version Control

Use Example:
-----------
from student.knowledge_graph import kg
kg.add_student('S1')
kg.add_concept('fractions-basic', name='Score base')
kg.add_concept('fraction-add', name='Plus')
kg.link_prerequisite('fractions-basic', 'fraction-add', weight=0.8)
kg.add_exercise('ex1', concepts={'fractions-basic':1.0}, difficulty=0.4)
kg.record_attempt('S1', 'ex1', correct=True, time_spent=32)
print(kg.get_mastery('S1', 'fractions-basic'))
print(kg.recommend_concepts('S1'))

Attention:
- This document is pure without dependence Python Structure appropriate for rapid integration and iterative。
- Under multiple threads, please place locks on the outer layer; no threads are currently secure。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import math
import time
import json
from pathlib import Path
from collections import defaultdict
from util.file_manager import get_file_manager
from student.global_methods import *
from student.cognitive_module.student import load_grade_knowledge_points
import re



# =============================
# Data class definitions
# =============================
@dataclass
class Concept:
    id: str
    name: Optional[str] = None
    parent_id: Optional[str] = None
    # tags: List[str] = field(default_factory=list)
    # metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Exercise:
    id: str
    difficulty: float = 0.5  # 0~1 Centre 0.5
    concepts: Dict[str, float] = field(default_factory=dict)  # concept_id -> weight
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Student:
    id: str
    profile: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Attempt:
    id: str
    student_id: str
    exercise_id: str
    correct: bool
    time_spent: float
    timestamp: float
    raw: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MasteryRecord:
    student_id: str
    concept_id: str
    concept_name: str
    misconceptions: List[str] = field(default_factory=list) # Myths
    p: float = 0.3                 # Initial mastery (Configureable)
    last_update: float = field(default_factory=lambda: time.time())
    stability: float = 0.0         # Reflects long-term consolidation
    streak: int = 0                # Count correctly and continuously
    decay_lambda: float = 0.04     # Forgotten Rate(days)

    def decay(self, now: Optional[float] = None) -> None:
        """Index decline: p <- p * exp(-λ * Δt)"""
        now = now or time.time()
        dt_days = (now - self.last_update) / 86400.0
        if dt_days <= 0:
            return
        self.p *= math.exp(-self.decay_lambda * dt_days / (1 + self.stability))
        self.p = max(0.01, min(0.99, self.p))
        self.last_update = now  # Update time immediately after decay to avoid multiple declines

# =============================
# Knowledge Mapping Main Category
# =============================
class KnowledgeGraph:
    def __init__(self):
        # Core packaging
        self.students: Dict[str, Student] = {}
        self.concepts: Dict[str, Concept] = {}
        self.exercises: Dict[str, Exercise] = {}
        self.prerequisites: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.attempts: List[Attempt] = []
        self.mastery: Dict[Tuple[str, str], MasteryRecord] = {}
        # Resources
        self._file_mgr = None  # Delay acquisition, avoiding circular import
        # Configure
        self.auto_save_enabled = True  # Autosave every update (overlay)）


    # ---------- Basic registration ----------
    def add_student(self, student_id: str, **profile):
        if student_id not in self.students:
            self.students[student_id] = Student(student_id, profile)
        else:
            self.students[student_id].profile.update(profile)

    def add_concept(self, concept_id: str, name: str, parent_id: str):
        if concept_id not in self.concepts:
            self.concepts[concept_id] = Concept(concept_id, name, parent_id)
        else:
            c = self.concepts[concept_id]
            c.name = name
            c.parent_id = parent_id
            # c.tags = list(set(c.tags).union(tags))
            # c.metadata.update(metadata)

    def link_prerequisite(self, pre_id: str, post_id: str, weight: float = 1.0):
        if pre_id not in self.concepts or post_id not in self.concepts:
            raise ValueError("Concept not registered: {}/{}".format(pre_id, post_id))
        self.prerequisites[pre_id][post_id] = max(0.0, min(1.0, weight))

    def add_exercise(self, exercise_id: str, *, concepts: Dict[str, float], difficulty: float = 0.5, **metadata):
        # Normalization of weights
        if not concepts:
            raise ValueError("The title must relate to at least one concept")
        total = sum(concepts.values())
        norm = {cid: w / total for cid, w in concepts.items()}
        # Validation concept exists
        for cid in norm.keys():
            if cid not in self.concepts:
                raise ValueError(f"Concept not registered: {cid}")
        self.exercises[exercise_id] = Exercise(exercise_id, difficulty, norm, metadata)

    # ---------- Mastery Visits ----------
    # Add myth, name
    def _get_or_create_mastery(self, student_id: str, concept_id: str,config_kg: dict, misconceptions: Optional[str] = None) -> MasteryRecord:
        key = (student_id, concept_id)
        rec = self.mastery.get(key)
        if rec is None:
            # From config_kg Getting conceptual names: config_kg[concept_id] = (name, parent_id)
            concept_name = config_kg.get(concept_id, (concept_id, None))[0]
            rec = MasteryRecord(
                student_id=student_id,
                concept_id=concept_id,
                concept_name=concept_name,
                misconceptions=[misconceptions] if misconceptions else []
            )
            self.mastery[key] = rec
        return rec

    def get_mastery(self, student_id: str, concept_id: str) -> Optional[float]:
        rec = self.mastery.get((student_id, concept_id))
        return rec.p if rec else None

    def get_student_profile_mastery(self, student_id: str) -> Dict[str, float]:
        return {rec.concept_name: rec.p for (sid, cid), rec in self.mastery.items() if sid == student_id}

    def get_student_profile_misconceptions(self, student_id: str) -> Dict[str, List[str]]:
        return {rec.concept_name: rec.misconceptions for (sid, cid), rec in self.mastery.items() if sid == student_id}

    # ---------- Attempt & Update ----------
    # TODO：If we follow up this part, we'll do it again。
    def record_attempt(
        self,
        student_id: str,
        exercise_id: str,
        *,
        correct: bool,
        time_spent: float,
        timestamp: Optional[float] = None,
        raw: Optional[Dict[str, Any]] = None,
        update: bool = True,
    persist_stream: bool = False,
    ) -> Attempt:
        if student_id not in self.students:
            raise ValueError(f"Students not registered: {student_id}")
        if exercise_id not in self.exercises:
            raise ValueError(f"Title not registered: {exercise_id}")
        timestamp = timestamp or time.time()
        attempt_id = f"{student_id}-{exercise_id}-{int(timestamp*1000)}"
        attempt = Attempt(
            id=attempt_id,
            student_id=student_id,
            exercise_id=exercise_id,
            correct=bool(correct),
            time_spent=float(time_spent),
            timestamp=timestamp,
            raw=raw or {},
        )
        self.attempts.append(attempt)
        if update:
            self._update_mastery_for_attempt(attempt)
        if persist_stream:
            # Write directly JSONL Stream (Write Simple Fields Only + mastery snapshot for involved concepts)
            if self._file_mgr is None:
                self._file_mgr = get_file_manager()
            mastery_snapshot = {
                cid: self.mastery[(student_id, cid)].p
                for cid in self.exercises[exercise_id].concepts.keys()
                if (student_id, cid) in self.mastery
            }
            self._file_mgr.append_knowledge_graph_attempt({
                "attempt_id": attempt.id,
                "student_id": student_id,
                "exercise_id": exercise_id,
                "correct": attempt.correct,
                "time_spent": attempt.time_spent,
                "timestamp": attempt.timestamp,
                "concepts": list(self.exercises[exercise_id].concepts.keys()),
                "mastery_after": mastery_snapshot,
            })
        # Automatically save (avoid generating mass snapshots: overwrite fixed files)）
        if self.auto_save_enabled:
            self._auto_save_compact()
        return attempt

    # Core update logic
    def _update_mastery_for_attempt(self, attempt: Attempt):
        ex = self.exercises[attempt.exercise_id]
        for cid, weight in ex.concepts.items():
            rec = self._get_or_create_mastery(attempt.student_id, cid)
            # 1. Decay
            rec.decay(now=attempt.timestamp)
            # 2. Logistic Incremental
            #   z = logit(p) + α*(outcome-0.5) + β*(0.5-difficulty) * weight Adjustment
            outcome = 1.0 if attempt.correct else 0.0
            z = math.log(rec.p / (1 - rec.p))
            alpha = 1.0 * weight          # Concept weight magnification
            beta = 0.6 * weight
            z_new = z + alpha * (outcome - 0.5) + beta * (0.5 - ex.difficulty)
            p_new = 1 / (1 + math.exp(-z_new))
            # 3. Straight streak & Stability
            if attempt.correct:
                rec.streak += 1
                if rec.streak >= 3:  # Reaching the threshold -> Increased stability and reduced forget rate
                    rec.streak = 0
                    rec.stability += 1
                    rec.decay_lambda *= 0.9  # It's slower to forget
            else:
                rec.streak = 0
                # Punishment for failure: Slightly down steady & Increasing the rate of forgetting(Upper limit)
                rec.stability = max(0.0, rec.stability - 0.2)
                rec.decay_lambda = min(0.08, rec.decay_lambda * 1.05)
            # 4. Border
            rec.p = max(0.01, min(0.99, p_new))
            rec.last_update = attempt.timestamp

    # ---------- Recommendations ----------
    def recommend_concepts(self, student_id: str, top_k: int = 5, mode: str = "weak") -> List[Tuple[str, float]]:
        """Recommended concepts based on model
        mode:
          weak: Minimum mastery (p Raise)
          reinforce: Medium(0.4~0.7) Priority (Nearest 0.55)
          review: Higher but unupdated
        """
        now = time.time()
        recs = []
        for cid in self.concepts:
            rec = self.mastery.get((student_id, cid))
            if not rec:
                # No practice -> High priority
                recs.append((cid, 0.0, 0.0, 999999))  # (cid, p, score, age)
                continue
            age_days = (now - rec.last_update) / 86400.0
            p = rec.p
            if mode == "weak":
                score = p  # Press directly p Raise
            elif mode == "reinforce":
                if 0.35 <= p <= 0.75:
                    score = abs(p - 0.55)  # The closer 0.55 The better -> Back in reverse
                else:
                    score = 999
            elif mode == "review":
                score = -age_days + (1 - p) * 0.2  # Time dominance + Small p Reconciliation
            else:
                score = p
            recs.append((cid, p, score, age_days))
        if mode == "weak":
            recs.sort(key=lambda x: x[1])  # p Raise
        elif mode == "reinforce":
            recs = [r for r in recs if r[2] != 999]
            recs.sort(key=lambda x: x[2])
        elif mode == "review":
            recs.sort(key=lambda x: x[2], reverse=True)
        # Back (concept_id, p)
        return [(cid, round(p, 4)) for cid, p, _, _ in recs[:top_k]]

    # ---------- Analysis / Statistics ----------
    def student_summary(self, student_id: str) -> Dict[str, Any]:
        ms = {cid: rec for (sid, cid), rec in self.mastery.items() if sid == student_id}
        if not ms:
            return {"student": student_id, "concepts_tracked": 0, "avg_mastery": None}
        avg_p = sum(r.p for r in ms.values()) / len(ms)
        return {
            "student": student_id,
            "concepts_tracked": len(ms),
            "avg_mastery": round(avg_p, 4),
            "low_concepts": [cid for cid, r in ms.items() if r.p < 0.4],
            "high_concepts": [cid for cid, r in ms.items() if r.p > 0.8],
        }

    # ---------- Passive learning (sensitization stage is not enhanced)） ----------
    # Add myths
    def passive_learn(self, student_id: str, concept_id: str, *, strength: float = 0.05, config_kg: dict, misconceptions: Optional[str] = None, timestamp: Optional[float] = None):
        """The passive exposure of students to a concept(Listening/Discussion)，Give me a little mastery。

        Rule:
        - Automatically create students & Concept mastery Records
        - First the decay, then the upgrade: p <- p + (1-p)*strength
        - stability Micro increment: +strength*0.5
        - strength Recommendations 0.01~0.15 Between
        - config_kg Format as Dictionary，{id: (name, parent_id)}
        """
        if student_id not in self.students:
            self.add_student(student_id)
        if concept_id not in self.concepts:
            self.add_concept(concept_id, name=config_kg.get(concept_id, (concept_id, None))[0], parent_id=config_kg.get(concept_id, (None, None))[1])
        # If the concept of ancestor exists, it is linked
        if self.concepts[concept_id].parent_id in self.concepts:
            parent_id = self.concepts[concept_id].parent_id
            # Create a forward relationship, default weight 0.3
            if concept_id not in self.prerequisites[parent_id]:
                self.link_prerequisite(parent_id, concept_id, weight=0.3)
        rec = self._get_or_create_mastery(student_id, concept_id, config_kg, misconceptions=misconceptions)
        ts = timestamp or time.time()
        # Add myths
        if misconceptions and misconceptions not in rec.misconceptions:
            rec.misconceptions.append(misconceptions)
        # Decline to current time point
        rec.decay(now=ts)
        strength = max(0.005, min(0.2, strength))
         # Raise 1 Close）
        rec.p = rec.p + (1 - rec.p) * strength
        rec.p = max(0.01, min(0.99, rec.p))
        rec.stability += strength * 0.5
        rec.last_update = ts
        if self.auto_save_enabled:
            self._auto_save_compact()

    # Add myths
    def batch_passive_learn(self, student_id: str, concept_ids: List[str], *, base_strength: float = 0.04, config_kg: dict, misconceptions: Optional[str] = None,importance: Optional[int] = None):
        """Mass Passive Learning，importance Can magnify overall strength。"""
        if not concept_ids:
            return
        factor = 1.0
        if importance is not None:
            # importance Expectations 1~10 In between, map to 0.5~1.5 Double
            factor = 0.5 + min(max(importance, 1), 10) / 10.0
        for cid in concept_ids:
            s = base_strength * factor
            self.passive_learn(student_id, cid, strength=s, config_kg=config_kg, misconceptions=misconceptions)
        # batch Internal passive_learn Triggered separately autosave；If you need to consolidate it, it can be changed to disable it internally

    # ---------- Automatically save realization ----------
    def _auto_save_compact(self):
        """Overwrite Single autosave File, avoid flashes。"""
        if self._file_mgr is None:
            self._file_mgr = get_file_manager()
        # Use __global__ & knowledge_graph Contents
        target_dir = self._file_mgr.get_category_dir('__global__', 'knowledge_graph')
        path = target_dir / 'kg_autosave.json'
        data = self.to_dict()
        data['metadata'] = {
            'type': 'autosave',
            'updated': time.time(),
            'students': len(self.students),
            'concepts': len(self.concepts),
            'exercises': len(self.exercises),
            'mastery_edges': len(self.mastery),
            'attempts': len(self.attempts)
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ---------- Enduring ----------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "students": {sid: s.profile for sid, s in self.students.items()},
            "concepts": {cid: {"name": c.name, "parent_id": c.parent_id} for cid, c in self.concepts.items()},
            "exercises": {
                eid: {"difficulty": e.difficulty, "concepts": e.concepts, "metadata": e.metadata}
                for eid, e in self.exercises.items()
            },
            "prerequisites": self.prerequisites,
            "mastery": {
                f"{sid}::{rec.concept_name}": {
                    "id": cid,
                    "misconceptions": rec.misconceptions,
                    "p": rec.p,
                    "last_update": rec.last_update,
                    "stability": rec.stability,
                    "streak": rec.streak,
                    "decay_lambda": rec.decay_lambda,
                }
                for (sid, cid), rec in self.mastery.items()
            },
            "attempts": [
                {
                    "id": a.id,
                    "student_id": a.student_id,
                    "exercise_id": a.exercise_id,
                    "correct": a.correct,
                    "time_spent": a.time_spent,
                    "timestamp": a.timestamp,
                }
                for a in self.attempts
            ],
        }

    def save_json(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    # ---- Integrated Unified File Manager Storage ----
    def snapshot(self, postfix: str = "") -> Path:
        """Adoption of projects file_manager Save Snapshot"""
        if self._file_mgr is None:
            self._file_mgr = get_file_manager()
        return self._file_mgr.save_knowledge_graph_snapshot(self, postfix=postfix)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeGraph':
        """Inverse sequenced knowledge mapping from dictionary data

        Support two data formats:

        1. Standard format (to_dict() Output):
           - students: {sid: profile_dict}
           - concepts: {cid: {"name": str, "parent_id": str}}
           - exercises: {eid: {"difficulty": float, "concepts": dict, "metadata": dict}}
           - prerequisites: {pre_id: {post_id: weight}}
           - mastery: {"sid::cid": {"p": float, "last_update": float, ...}}
           - attempts: [{"id": str, "student_id": str, ...}] (Optional)

        2. nodes.json Format (Memory system):
           - node_1: {"type": "knowledge", "knowledge_tag": [...], "content": "...", ...}
           - node_2: {"type": "chat", ...}
           ...
           When this format is detected,From type="knowledge" , the concept of extraction in the node
        """
        kg = cls()

        # Test Data Format: If all the keys are "node_X" Format,Yes nodes.json
        is_nodes_format = False
        if data:
            sample_keys = list(data.keys())[:5]  # Before checking 5 Key
            is_nodes_format = all(key.startswith("node_") for key in sample_keys)

        if is_nodes_format:
            # From nodes.json Format Restore - Extract All type="knowledge" ♪ The nodes and put knowledge_tag Each one in the list as a concept
            for node_id, node_data in data.items():
                if not isinstance(node_data, dict):
                    continue

                node_type = node_data.get("type")
                if node_type != "knowledge":
                    continue

                knowledge_tags = node_data.get("knowledge_tag")
                if not knowledge_tags:
                    # Some knowledge nodes may be labeled keywords Or content Pending
                    continue

                # knowledge_tag Could be a list or a single string
                tags = []
                if isinstance(knowledge_tags, list):
                    tags = knowledge_tags
                elif isinstance(knowledge_tags, str):
                    tags = [knowledge_tags]

                for concept_name in tags:
                    if not isinstance(concept_name, str):
                        continue
                    concept_name = concept_name.strip()
                    if not concept_name:
                        continue

                    # Generating concepts ID: Replace space with underlined, Replace the character of other non-alphatic hyphens with the underlined
                    candidate = re.sub(r"\s+", "_", concept_name)
                    candidate = re.sub(r"[^0-9A-Za-z_\-]", "_", candidate)
                    concept_id = candidate

                    # To avoid repeating the same concept
                    if concept_id not in kg.concepts:
                        kg.concepts[concept_id] = Concept(
                            id=concept_id,
                            name=concept_name,
                            parent_id=None  # nodes.json There is usually no level information
                        )

        else:
            # Restore from Standard Format
            # 1. Rehabilitation of students
            for sid, profile in data.get('students', {}).items():
                kg.add_student(sid, **profile)

            # 2. Restoration of concepts (all concepts must be restored before a pre-existing relationship is established)）
            for cid, cdata in data.get('concepts', {}).items():
                kg.add_concept(
                    concept_id=cid,
                    name=cdata.get('name', cid),  # If not name，Use id As name
                    parent_id=cdata.get('parent_id')  # parent_id Yes None
                )

            # 3. Restore Title
            for eid, edata in data.get('exercises', {}).items():
                kg.add_exercise(
                    exercise_id=eid,
                    concepts=edata.get('concepts', {}),
                    difficulty=edata.get('difficulty', 0.5),
                    **edata.get('metadata', {})
                )

            # 4. Restore Forward Relationships
            # prerequisites Format: {pre_id: {post_id: weight, ...}, ...}
            prereqs = data.get('prerequisites', {})
            if isinstance(prereqs, dict):
                kg.prerequisites = defaultdict(dict)
                for pre_id, posts in prereqs.items():
                    if isinstance(posts, dict):
                        for post_id, weight in posts.items():
                            kg.prerequisites[pre_id][post_id] = weight

            # 5. Restoration of mastery records
            for key, m in data.get('mastery', {}).items():
                # Parsing Composite Key "sid::concept_name"
                if '::' not in key:
                    continue  # Skip an incorrect format key

                parts = key.split('::', 1)
                if len(parts) != 2:
                    continue

                sid, concept_name = parts  # Attention: Here's the key concept_name, Nope concept_id

                # Get real from the data concept_id
                concept_id = m.get('id')
                if not concept_id:
                    continue  # If not id Fields,Skip

                # Create mastery record (Note parameter order: student_id, concept_id, concept_name)
                rec = MasteryRecord(sid, concept_id, concept_name)
                rec.misconceptions = m.get('misconceptions', [])
                rec.p = m.get('p', 0.3)
                rec.last_update = m.get('last_update', time.time())
                rec.stability = m.get('stability', 0.0)
                rec.streak = m.get('streak', 0)
                rec.decay_lambda = m.get('decay_lambda', 0.04)

                # Attention: mastery The key is (student_id, concept_id), Nope concept_name
                kg.mastery[(sid, concept_id)] = rec

            # 6. Restore attempts（Optional, usually with large historical records, recoverable as needed）
            for a_data in data.get('attempts', []):
                attempt = Attempt(
                    id=a_data.get('id', ''),
                    student_id=a_data.get('student_id', ''),
                    exercise_id=a_data.get('exercise_id', ''),
                    correct=a_data.get('correct', False),
                    time_spent=a_data.get('time_spent', 0.0),
                    timestamp=a_data.get('timestamp', time.time()),
                    raw=a_data.get('raw', {})
                )
                kg.attempts.append(attempt)

        return kg

    @classmethod
    def load_json(cls, path: str | Path) -> 'KnowledgeGraph':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)

    # ---- Search for knowledge maps ----
    def get_id_by_name(self, target_name: str, config_kg: dict) -> Optional[str]:
        """Based on config_kp, Getting the concept by name ID（Returns the first match）"""
        for cid, (name, parent_id) in config_kg.items():
            if name == target_name:
                return cid
        return None

    def get_batch_id_by_names(self, target_names: List[str], config_kg: dict) -> List[str]:
        """Batch of concepts based on name of knowledge point ID List"""
        ids = []
        name_to_id = {name: cid for cid, (name, _) in config_kg.items()}
        for name in target_names:
            if name in name_to_id:
                ids.append(name_to_id[name])
        return ids

# Single instance (Enable direct import use)
kg = KnowledgeGraph()

# If you need access to an existing response process,：
# 1. Call after processing each issue kg.record_attempt(student_id, exercise_id, correct=..., time_spent=..., raw=answer_dict)
# 2. The title needs to be adopted in advance kg.add_exercise Registration (one-time registration at loading library)）
# 3. Output while saving statistics kg.student_summary(student.name)

if __name__ == '__main__':  # Simple self-measurement
    kg.add_student('S1')
    kg.add_concept('c1', name='Score base')
    kg.add_concept('c2', name='Plus')
    kg.link_prerequisite('c1', 'c2', 0.8)
    kg.add_exercise('e1', concepts={'c1': 1.0}, difficulty=0.5)
    kg.add_exercise('e2', concepts={'c1': 0.4, 'c2': 0.6}, difficulty=0.6)
    for i in range(5):
        kg.record_attempt('S1', 'e1', correct=(i % 2 == 0), time_spent=30)
    kg.record_attempt('S1', 'e2', correct=True, time_spent=45)
    print('Summary:', kg.student_summary('S1'))
    print('Recommend (weak):', kg.recommend_concepts('S1', mode='weak'))
    p = kg.get_mastery('S1', 'c1')
    print('Mastery c1:', p)
