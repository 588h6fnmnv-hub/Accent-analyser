"""VoiceLens Storage for analysis history."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
import uuid


class AnalysisStorage:
    """Manages persistent storage of analysis results using SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".local" / "share" / "voicelens" / "history.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    audio_duration_seconds REAL,
                    transcript_text TEXT,
                    transcript_language TEXT,
                    word_count INTEGER,
                    accent_predicted TEXT,
                    accent_confidence REAL,
                    pronunciation_overall_score REAL,
                    pronunciation_similarity REAL,
                    pronunciation_confidence REAL,
                    pronunciation_backend TEXT,
                    metrics_json TEXT,
                    filler_words_json TEXT,
                    repeated_words_json TEXT,
                    difficult_words_json TEXT,
                    feedback_json TEXT,
                    full_result_json TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at ON analyses(created_at DESC)
            """)
            conn.commit()

    def save(self, result: dict) -> str:
        """Save analysis result to database."""
        analysis_id = result.get("id", f"vl-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}")

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO analyses (
                    id, created_at, audio_duration_seconds,
                    transcript_text, transcript_language, word_count,
                    accent_predicted, accent_confidence,
                    pronunciation_overall_score, pronunciation_similarity,
                    pronunciation_confidence, pronunciation_backend,
                    metrics_json, filler_words_json, repeated_words_json,
                    difficult_words_json, feedback_json, full_result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis_id,
                result.get("createdAt", datetime.now().isoformat()),
                result.get("audioDurationSeconds", 0.0),
                result.get("transcript", {}).get("text", ""),
                result.get("transcript", {}).get("language", "English"),
                result.get("transcript", {}).get("wordCount", 0),
                result.get("accent", {}).get("predictedAccent", "Unknown"),
                result.get("accent", {}).get("confidence", 0.0),
                result.get("pronunciation", {}).get("overallScore", 0.0),
                result.get("pronunciation", {}).get("pronunciationSimilarity", 0.0),
                result.get("pronunciation", {}).get("confidence", 0.0),
                result.get("pronunciation", {}).get("backend", "unknown"),
                json.dumps(result.get("metrics", {})),
                json.dumps(result.get("fillerWordsList", [])),
                json.dumps(result.get("repeatedWordsList", [])),
                json.dumps(result.get("difficultWordsList", [])),
                json.dumps(result.get("overallFeedback", [])),
                json.dumps(result),
            ))
            conn.commit()

        return analysis_id

    def get(self, analysis_id: str) -> Optional[dict]:
        """Get analysis by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT full_result_json FROM analyses WHERE id = ?",
                (analysis_id,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row["full_result_json"])
        return None

    def get_all(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Get all analyses, most recent first."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT full_result_json FROM analyses ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            return [json.loads(row["full_result_json"]) for row in cursor.fetchall()]

    def delete(self, analysis_id: str) -> bool:
        """Delete analysis by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
            conn.commit()
            return cursor.rowcount > 0

    def count(self) -> int:
        """Get total count of analyses."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM analyses")
            return cursor.fetchone()[0]

    def clear_all(self) -> int:
        """Clear all analyses."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM analyses")
            conn.commit()
            return cursor.rowcount