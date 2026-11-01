from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=100,
        validation_alias=AliasChoices("full_name", "name"),
    )
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: int
    full_name: str
    name: Optional[str] = None
    email: EmailStr
    role: str

    def model_post_init(self, __context):
        if self.name is None:
            self.name = self.full_name


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# Alias for backwards compatibility
TokenResponse = AuthResponse


class QuestionCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    body: str = Field(
        min_length=1,
        max_length=5000,
        validation_alias=AliasChoices("body", "description"),
    )
    category: Optional[str] = Field(default="General", max_length=100)
    force_create: bool = False


class SimilarQuestionResponse(BaseModel):
    id: int
    title: str
    body: str
    category: str = "General"
    similarity: float
    similarity_percent: int
    possible_duplicate: bool = False


class SimilarQuestionsResponse(BaseModel):
    matches: list[SimilarQuestionResponse]
    suggestion_threshold: float
    duplicate_threshold: float


class QuestionUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=5, max_length=200)
    body: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=5000,
        validation_alias=AliasChoices("body", "description"),
    )
    category: Optional[str] = Field(default=None, max_length=100)


class QuestionResponse(BaseModel):
    id: int
    title: str
    body: str
    description: Optional[str] = None
    category: str
    author_id: int
    author_name: Optional[str] = None
    votes: int = 0
    answers: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def model_post_init(self, __context):
        if self.description is None:
            self.description = self.body


class AnswerCreate(BaseModel):
    body: str = Field(
        min_length=1,
        max_length=5000,
        validation_alias=AliasChoices("body", "content"),
    )


class AnswerUpdate(BaseModel):
    body: str = Field(
        min_length=1,
        max_length=5000,
        validation_alias=AliasChoices("body", "content"),
    )


class AnswerVerificationUpdate(BaseModel):
    verified: bool


class AnswerResponse(BaseModel):
    id: int
    question_id: int
    author_id: int
    author_name: Optional[str] = None
    body: str
    content: Optional[str] = None
    faculty_verified: bool = False
    helpful_votes: int = 0
    ranking_score: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def model_post_init(self, __context):
        if self.content is None:
            self.content = self.body


def _validate_http_url(value: Optional[str]) -> Optional[str]:
    """Only allow http(s) links so stored URLs can never be javascript:/data: payloads."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > 2048:
        raise ValueError("URL is too long")
    if not value.lower().startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")
    return value


class ResourceCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=3000)
    url: Optional[str] = None

    @field_validator("url")
    @classmethod
    def _check_url(cls, v):
        return _validate_http_url(v)
    category: Optional[str] = Field(default="Academic", max_length=100)


class ResourceUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, min_length=1, max_length=3000)
    url: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=100)

    @field_validator("url")
    @classmethod
    def _check_url(cls, v):
        return _validate_http_url(v)


class ResourceResponse(BaseModel):
    id: int
    title: str
    description: str
    category: str
    url: Optional[str] = None
    author_id: int
    author_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NoticeCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(
        min_length=1,
        max_length=5000,
        validation_alias=AliasChoices("body", "content"),
    )
    category: Optional[str] = Field(default="General", max_length=100)


class NoticeUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    body: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=5000,
        validation_alias=AliasChoices("body", "content"),
    )
    category: Optional[str] = Field(default=None, max_length=100)


class NoticeResponse(BaseModel):
    id: int
    title: str
    body: str
    content: Optional[str] = None
    category: str = "General"
    created_by: int
    author_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def model_post_init(self, __context):
        if self.content is None:
            self.content = self.body


class ProcedureCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=3000)
    content: str = Field(min_length=1, max_length=10000)
    verified: bool = True


class ProcedureUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, min_length=1, max_length=3000)
    content: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    verified: Optional[bool] = None


class ProcedureResponse(BaseModel):
    id: int
    title: str
    description: str
    content: str
    created_by: int
    creator_name: Optional[str] = None
    verified: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class HelpRequestCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    category: Optional[str] = Field(default="General", max_length=100)


class HelpRequestUpdate(BaseModel):
    status: str = Field(pattern="^(open|resolved)$")


class HelpRequestResponse(BaseModel):
    id: int
    title: str
    description: str
    category: str
    author_id: int
    author_name: Optional[str] = None
    status: str = "open"
    helpers: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RoleUpdate(BaseModel):
    role: str = Field(pattern="^(student|faculty|admin)$")


class AdminStats(BaseModel):
    users: int
    questions: int
    answers: int
    resources: int
    notices: int
    help_requests: int
