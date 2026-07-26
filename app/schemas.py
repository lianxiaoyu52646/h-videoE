from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class UserRead(BaseModel):
    id: int
    username: Optional[str] = None
    email: str = ""
    display_name: str = ""
    avatar_url: Optional[str] = None
    is_default: bool = False
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenCreateRequest(BaseModel):
    label: str = "extension"


class AuthResponse(BaseModel):
    user: UserRead
    token: Optional[str] = None


class WordBookStudyProgress(BaseModel):
    total: int = 0
    learned: int = 0
    unknown: int = 0
    cursor: int = 0
    percent: float = 0
    label: str = "0 / 0"


class WordBookStudyFeed(BaseModel):
    wordbook_id: int
    name: str
    items: list[dict]
    progress: WordBookStudyProgress
    has_more: bool = True
    has_more_before: bool = False
    has_more_after: bool = True
    offset: int = 0


class WordBookStudyCommit(BaseModel):
    entry_ids: list[int] = Field(default_factory=list)
    starred_ids: list[int] = Field(default_factory=list)


class WordBookStudyCursor(BaseModel):
    cursor: int = 0


class WordBookStudyStar(BaseModel):
    entry_id: int
    starred: bool = True


class VideoCreate(BaseModel):
    url: str


class VideoRead(BaseModel):
    id: int
    url: str
    source: str
    video_id: Optional[str] = None
    embed_url: Optional[str] = None
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    created_at: datetime
    subtitle_status: str = "pending"
    progress: int = 0
    status_message: str = ""
    duration_seconds: float = 0
    subtitle_count: int = 0
    active_job_id: Optional[int] = None
    learn_phase: str = "metadataReady"

    model_config = {"from_attributes": True}


class SubtitleRead(BaseModel):
    id: int
    video_id: int
    start: float
    end: float
    text: str
    translation: Optional[str] = None

    model_config = {"from_attributes": True}


class SubtitleFocusRequest(BaseModel):
    anchor_id: Optional[int] = None
    subtitle_ids: list[int] = Field(default_factory=list)


class JobRead(BaseModel):
    id: int
    kind: str
    status: str
    progress: int
    message: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AppShellRead(BaseModel):
    app_name: str
    app_mode: str
    desktop_mode: bool
    supports_login: bool
    supports_extension: bool
    profile_name: str
    desktop_base_url: str
    mobile_home: bool = False
    features: list[str] = []


class AppVersionRead(BaseModel):
    """Client update check: web content vs native APK shell."""
    web_content_version: str
    android_version_code: int = 1
    android_version_name: str = "1.0.0"
    android_apk_url: str = ""
    notes: str = ""
    force_apk: bool = False


class WordRead(BaseModel):
    word: str
    lemma: Optional[str] = None
    definition: str
    pronunciation: Optional[str] = None
    part_of_speech: Optional[str] = None
    example: Optional[str] = None
    translation: Optional[str] = None
    youdao_translation: Optional[str] = None
    lookup_source: str = "miss"
    matched_word: Optional[str] = None
    suggestions: list[str] = []
    pending_enrichment: bool = False


class VocabCreate(BaseModel):
    word: str
    wordbook_id: Optional[int] = None


class VocabSaveContext(BaseModel):
    word: str
    source_platform: str
    source_video_id: str = ""
    source_url: str = ""
    source_title: Optional[str] = None
    sentence: Optional[str] = None
    sentence_translation: Optional[str] = None
    timestamp: Optional[float] = None
    definition: Optional[str] = None
    pronunciation: Optional[str] = None
    part_of_speech: Optional[str] = None
    translation: Optional[str] = None
    wordbook_id: Optional[int] = None


class VocabContextRead(BaseModel):
    id: int
    source_platform: str
    source_video_id: Optional[str] = None
    source_url: str = ""
    source_title: Optional[str] = None
    sentence: Optional[str] = None
    sentence_translation: Optional[str] = None
    timestamp: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VocabRead(BaseModel):
    id: int
    word: str
    lemma: Optional[str] = None
    definition: str
    pronunciation: Optional[str] = None
    part_of_speech: Optional[str] = None
    example: Optional[str] = None
    translation: Optional[str] = None
    source_platform: Optional[str] = None
    source_video_id: Optional[str] = None
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    sentence: Optional[str] = None
    sentence_translation: Optional[str] = None
    timestamp: Optional[float] = None
    wordbook_id: Optional[int] = None
    stability: float
    difficulty: float
    reps: int
    lapses: int
    state: int
    scheduled_days: int
    last_review: Optional[datetime] = None
    due: datetime
    added_at: datetime
    contexts_count: int = 0
    review_count: int = 0

    model_config = {"from_attributes": True}


class VideoVocabSummary(BaseModel):
    source_video_id: str
    source_title: Optional[str] = None
    source_platform: Optional[str] = None
    source_url: Optional[str] = None
    word_count: int


class TranslateBatchRequest(BaseModel):
    texts: list[str]
    source: str = "en"
    target: str = "zh-CN"


class ReviewRequest(BaseModel):
    vocab_id: int
    rating: int


class ReviewLogRead(BaseModel):
    id: int
    rating: int
    reviewed_at: datetime
    due_before: Optional[datetime] = None
    due_after: Optional[datetime] = None
    scheduled_days_after: int
    stability_after: float
    difficulty_after: float

    model_config = {"from_attributes": True}


class ReadingCreate(BaseModel):
    title: str = "Untitled"
    content: str
    source_type: str = "paste"
    source_url: Optional[str] = None
    source_filename: Optional[str] = None


class ReadingBlockRead(BaseModel):
    id: int
    document_id: int
    order_index: int
    text: str
    translation: Optional[str] = None
    section_title: Optional[str] = None

    model_config = {"from_attributes": True}


class ReadingBlocksPage(BaseModel):
    items: list[ReadingBlockRead]
    offset: int
    limit: int
    total: int
    has_more: bool


class ReadingRead(BaseModel):
    id: int
    title: str
    created_at: datetime
    block_count: int = 0
    word_count: int = 0
    translate_status: str = "pending"
    translate_progress: int = 0
    translated_blocks: int = 0
    status_message: str = ""
    last_block_index: int = 0
    read_progress: int = 0
    source_type: str = "paste"
    source_url: Optional[str] = None
    source_filename: Optional[str] = None
    active_job_id: Optional[int] = None

    @field_validator("source_type", "status_message", mode="before")
    @classmethod
    def _none_to_default_str(cls, value, info):
        if value is None:
            return "paste" if info.field_name == "source_type" else ""
        return value

    model_config = {"from_attributes": True}


class ReadingProgressUpdate(BaseModel):
    block_index: int


class ReadingUpdate(BaseModel):
    title: str


class VocabMigrateRequest(BaseModel):
    from_source_id: str
    source_platform: str = "reading"
    source_url: str = ""
    source_title: Optional[str] = None


class HighlightCreate(BaseModel):
    block_id: int
    start_offset: int
    end_offset: int
    selected_text: str
    color: str = "yellow"


class HighlightRead(BaseModel):
    id: int
    document_id: int
    block_id: int
    start_offset: int
    end_offset: int
    selected_text: str
    color: str
    created_at: datetime

    model_config = {"from_attributes": True}


class NoteCreate(BaseModel):
    block_id: Optional[int] = None
    highlight_id: Optional[int] = None
    content: str


class NoteUpdate(BaseModel):
    content: str


class NoteRead(BaseModel):
    id: int
    document_id: int
    block_id: Optional[int] = None
    highlight_id: Optional[int] = None
    block_index: Optional[int] = None
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookmarkCreate(BaseModel):
    block_index: int
    label: str = ""


class BookmarkUpdate(BaseModel):
    label: str


class BookmarkRead(BaseModel):
    id: int
    document_id: int
    block_index: int
    label: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReadingSearchHit(BaseModel):
    block_id: int
    order_index: int
    section_title: Optional[str] = None
    snippet: str
    match_start: int
    match_end: int


class ReadingVocabStats(BaseModel):
    words: list[str]
    word_count: int
    due_count: int


class ReadingChapterRead(BaseModel):
    chapter_index: int
    title: str
    start_block: int
    end_block: int
    block_count: int

    model_config = {"from_attributes": True}


class ReadingToc(BaseModel):
    chapters: list[ReadingChapterRead]
    chapter_count: int = 0
    block_count: int = 0


class ReadingChapterBlocksPage(BaseModel):
    chapter: ReadingChapterRead
    items: list[ReadingBlockRead]
    offset: int
    limit: int
    total: int
    has_more: bool


class ReadingBootstrap(BaseModel):
    doc: ReadingRead
    blocks: list[ReadingBlockRead]
    chapters: list[ReadingChapterRead] = []
    chapter_index: int = 0
    highlights: list[HighlightRead]
    notes: list[NoteRead]
    bookmarks: list[BookmarkRead]
    vocab_stats: ReadingVocabStats
    blocks_offset: int = 0
    blocks_limit: int = 50
    blocks_total: int = 0
    has_more_blocks: bool = False
    chapter_block_total: int = 0
    has_more_chapters: bool = False


class WordBookCreate(BaseModel):
    name: str
    description: str = ""
    language: str = "en"
    source_name: str = ""


class WordBookRead(BaseModel):
    id: int
    name: str
    description: str
    language: str
    source_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    entry_count: int = 0
    learned_count: int = 0
    study_seen: int = 0
    study_percent: float = 0.0
    study_label: str = ""

    model_config = {"from_attributes": True}


class WordBookCatalogRead(BaseModel):
    id: int
    key: str
    provider: str
    name: str
    description: str
    source_name: Optional[str] = None
    repo_url: str
    raw_url: str
    asset_file: str
    entry_count: int = 0
    category: str = ""
    installed_wordbook_id: Optional[int] = None
    installed_at: Optional[datetime] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class WordBookEntryCreate(BaseModel):
    word: str
    lemma: Optional[str] = None
    definition: str = ""
    translation: Optional[str] = None
    pronunciation: Optional[str] = None
    part_of_speech: Optional[str] = None
    example: Optional[str] = None
    tags: list[str] = []
    level: Optional[str] = None


class WordBookEntryRead(BaseModel):
    id: int
    wordbook_id: int
    word: str
    lemma: Optional[str] = None
    definition: str
    translation: Optional[str] = None
    pronunciation: Optional[str] = None
    part_of_speech: Optional[str] = None
    example: Optional[str] = None
    tags: list[str] = []
    level: Optional[str] = None

    model_config = {"from_attributes": True}


class WordBookEntriesPage(BaseModel):
    items: list[WordBookEntryRead]
    page: int
    page_size: int
    total: int
    total_pages: int
    query: str = ""


class WordBookAddWordRequest(BaseModel):
    word: str


class WordBookImportResult(BaseModel):
    ok: bool = True
    count: int = 0
    parsed: int = 0
    filename: str = ""


class WordBookImportRequest(BaseModel):
    entries: list[WordBookEntryCreate]


class LibraryBookRead(BaseModel):
    id: int
    key: str
    provider: str
    title: str
    author: str
    description: str
    language: str = "en"
    repo_url: str
    raw_url: str
    tags: list[str] = []
    cache_status: str = "pending"
    cache_path: Optional[str] = None
    cache_sha256: Optional[str] = None
    cache_bytes: int = 0
    last_error: Optional[str] = None
    reading_document_id: Optional[int] = None
    imported_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    reading_translate_status: Optional[str] = None
    reading_translate_progress: int = 0
    reading_translated_blocks: int = 0
    reading_block_count: int = 0
    reading_read_progress: int = 0
    reading_status_message: str = ""

    model_config = {"from_attributes": True}


class PracticeQuestion(BaseModel):
    type: str
    word: Optional[str] = None
    definition: Optional[str] = None
    pronunciation: Optional[str] = None
    question: str
    answer: str
    choices: Optional[list[str]] = None
