from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, JSON, Text, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str = Field(default="")
    display_name: str = Field(default="")
    is_active: bool = Field(default=True)
    is_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ApiToken(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("token_hash", name="uq_api_token_hash"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    label: str = Field(default="default")
    token_prefix: str = Field(default="", index=True)
    token_hash: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class PlatformCredential(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_platform_credential"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    provider: str = Field(index=True)
    username: Optional[str] = None
    credential_json: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_verified_at: Optional[datetime] = None


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    kind: str = Field(index=True)
    status: str = Field(default="pending", index=True)
    progress: int = Field(default=0)
    message: str = Field(default="")
    target_type: Optional[str] = Field(default=None, index=True)
    target_id: Optional[int] = Field(default=None, index=True)
    payload_json: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
    )
    result_json: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class Video(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(default=1, foreign_key="user.id", index=True)
    url: str = Field(index=True)
    source: str = "generic"
    video_id: Optional[str] = None
    embed_url: Optional[str] = None
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    subtitle_status: str = Field(default="pending")
    progress: int = Field(default=0)
    status_message: str = Field(default="")
    duration_seconds: float = Field(default=0)
    active_job_id: Optional[int] = Field(default=None, foreign_key="job.id")
    subtitles: List["Subtitle"] = Relationship(back_populates="video")


class Subtitle(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="video.id", index=True)
    start: float
    end: float
    text: str
    translation: Optional[str] = None
    video: Optional[Video] = Relationship(back_populates="subtitles")


class ReadingDocument(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(default=1, foreign_key="user.id", index=True)
    title: str = Field(default="Untitled")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    block_count: int = Field(default=0)
    word_count: int = Field(default=0)
    translate_status: str = Field(default="pending")
    translate_progress: int = Field(default=0)
    translated_blocks: int = Field(default=0)
    status_message: str = Field(default="")
    last_block_index: int = Field(default=0)
    read_progress: int = Field(default=0)
    source_type: str = Field(default="paste")
    source_url: Optional[str] = None
    source_filename: Optional[str] = None
    active_job_id: Optional[int] = Field(default=None, foreign_key="job.id")
    deleted_at: Optional[datetime] = Field(default=None, index=True)
    blocks: List["ReadingBlock"] = Relationship(back_populates="document")


class TranslationCache(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    text_hash: str = Field(index=True, unique=True)
    translation: str = Field(default="")
    hit_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DictionaryEntryCache(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("word", "source_name", name="uq_dictionary_cache_word_source"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    word: str = Field(index=True)
    lemma: Optional[str] = Field(default=None, index=True)
    source_name: str = Field(default="online-cache", index=True)
    entry_json: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReadingBlock(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="readingdocument.id", index=True)
    order_index: int = Field(default=0, index=True)
    text: str = Field(sa_column=Column(Text, nullable=False))
    translation: Optional[str] = Field(default=None, sa_column=Column(Text))
    section_title: Optional[str] = None
    text_hash: Optional[str] = Field(default=None, index=True)
    document: Optional[ReadingDocument] = Relationship(back_populates="blocks")


class ReadingChapter(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("document_id", "chapter_index", name="uq_reading_chapter_doc_idx"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="readingdocument.id", index=True)
    chapter_index: int = Field(default=0, index=True)
    title: str = Field(default="")
    start_block: int = Field(default=0, index=True)
    end_block: int = Field(default=0, index=True)
    block_count: int = Field(default=0)


class ReadingHighlight(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(default=1, foreign_key="user.id", index=True)
    document_id: int = Field(foreign_key="readingdocument.id", index=True)
    block_id: int = Field(foreign_key="readingblock.id", index=True)
    start_offset: int = Field(default=0)
    end_offset: int = Field(default=0)
    selected_text: str = Field(default="")
    color: str = Field(default="yellow")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReadingNote(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(default=1, foreign_key="user.id", index=True)
    document_id: int = Field(foreign_key="readingdocument.id", index=True)
    block_id: Optional[int] = Field(default=None, foreign_key="readingblock.id")
    highlight_id: Optional[int] = Field(default=None, foreign_key="readinghighlight.id")
    content: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReadingBookmark(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(default=1, foreign_key="user.id", index=True)
    document_id: int = Field(foreign_key="readingdocument.id", index=True)
    block_index: int = Field(default=0)
    label: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WordBook(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_wordbook_user_name"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(default=1, foreign_key="user.id", index=True)
    name: str = Field(index=True)
    description: str = Field(default="")
    language: str = Field(default="en")
    source_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(default=None, index=True)


class WordBookEntry(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("wordbook_id", "word", name="uq_wordbook_entry_word"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    wordbook_id: int = Field(foreign_key="wordbook.id", index=True)
    word: str = Field(index=True)
    lemma: Optional[str] = None
    definition: str = Field(default="")
    translation: Optional[str] = None
    pronunciation: Optional[str] = None
    part_of_speech: Optional[str] = None
    example: Optional[str] = None
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )
    level: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WordBookCatalog(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_wordbook_catalog_user_key"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(default=1, foreign_key="user.id", index=True)
    key: str = Field(index=True)
    provider: str = Field(default="github", index=True)
    name: str = Field(default="")
    description: str = Field(default="")
    source_name: Optional[str] = None
    repo_url: str = Field(default="")
    raw_url: str = Field(default="")
    asset_file: str = Field(default="")
    entry_count: int = Field(default=0)
    installed_wordbook_id: Optional[int] = Field(default=None, foreign_key="wordbook.id", index=True)
    installed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LibraryBook(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_library_book_user_key"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(default=1, foreign_key="user.id", index=True)
    key: str = Field(index=True)
    provider: str = Field(default="github", index=True)
    title: str = Field(default="", index=True)
    author: str = Field(default="")
    description: str = Field(default="")
    language: str = Field(default="en")
    repo_url: str = Field(default="")
    raw_url: str = Field(default="")
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )
    cache_status: str = Field(default="pending", index=True)
    cache_path: Optional[str] = None
    cache_sha256: Optional[str] = None
    cache_bytes: int = Field(default=0)
    last_error: Optional[str] = Field(default=None, sa_column=Column(Text))
    reading_document_id: Optional[int] = Field(default=None, foreign_key="readingdocument.id", index=True)
    imported_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class VocabItem(SQLModel, table=True):
    __tablename__ = "vocabcard"
    __table_args__ = (UniqueConstraint("user_id", "word", name="uq_vocab_user_word"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(default=1, foreign_key="user.id", index=True)
    word: str = Field(index=True)
    lemma: Optional[str] = Field(default=None, index=True)
    definition: str = Field(default="")
    pronunciation: Optional[str] = None
    part_of_speech: Optional[str] = None
    example: Optional[str] = None
    translation: Optional[str] = None
    added_at: datetime = Field(default_factory=datetime.utcnow)
    source_platform: Optional[str] = Field(default=None, index=True)
    source_video_id: Optional[str] = Field(default=None, index=True)
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    sentence: Optional[str] = None
    sentence_translation: Optional[str] = None
    timestamp: Optional[float] = None
    wordbook_id: Optional[int] = Field(default=None, foreign_key="wordbook.id", index=True)
    stability: float = Field(default=0)
    difficulty: float = Field(default=0)
    elapsed_days: int = Field(default=0)
    scheduled_days: int = Field(default=0)
    reps: int = Field(default=0)
    lapses: int = Field(default=0)
    state: int = Field(default=0)
    last_review: Optional[datetime] = None
    due: datetime = Field(default_factory=datetime.utcnow)
    contexts: List["VocabContext"] = Relationship(back_populates="vocab")
    review_logs: List["ReviewLog"] = Relationship(back_populates="vocab")


class VocabContext(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(default=1, foreign_key="user.id", index=True)
    vocab_id: int = Field(foreign_key="vocabcard.id", index=True)
    source_platform: str = Field(default="manual", index=True)
    source_video_id: Optional[str] = Field(default=None, index=True)
    source_url: str = Field(default="")
    source_title: Optional[str] = None
    sentence: Optional[str] = Field(default=None, sa_column=Column(Text))
    sentence_translation: Optional[str] = Field(default=None, sa_column=Column(Text))
    timestamp: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    vocab: Optional[VocabItem] = Relationship(back_populates="contexts")


class ReviewLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(default=1, foreign_key="user.id", index=True)
    vocab_id: int = Field(foreign_key="vocabcard.id", index=True)
    rating: int = Field(default=3)
    reviewed_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    due_before: Optional[datetime] = None
    due_after: Optional[datetime] = None
    scheduled_days_after: int = Field(default=0)
    stability_after: float = Field(default=0)
    difficulty_after: float = Field(default=0)
    vocab: Optional[VocabItem] = Relationship(back_populates="review_logs")


VocabCard = VocabItem
