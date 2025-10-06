from typing import Literal, Optional

from pydantic import BaseModel, Field


# Shared config allowing extra fields so recorder payloads pass through
class _BaseExtra(BaseModel):
	"""Base model ignoring unknown fields."""

	class Config:
		extra = 'ignore'


# Mixin for shared step metadata (timestamp and tab context)
class StepMeta(_BaseExtra):
	timestamp: Optional[int] = Field(None, description='Timestamp from recording (informational).')
	tabId: Optional[int] = Field(None, description='Browser tab ID from recording (informational).')


# Common optional fields present in recorder events
class RecorderBase(StepMeta):
	xpath: Optional[str] = None
	elementTag: Optional[str] = None
	elementText: Optional[str] = None
	frameUrl: Optional[str] = None
	screenshot: Optional[str] = None


class ClickElementDeterministicAction(RecorderBase):
	"""Parameters for clicking an element identified by CSS selector."""

	type: Literal['click']
	cssSelector: str


class InputTextDeterministicAction(RecorderBase):
	"""Parameters for entering text into an input field identified by CSS selector."""

	type: Literal['input']
	cssSelector: str
	value: str


class SelectDropdownOptionDeterministicAction(RecorderBase):
	"""Parameters for selecting a dropdown option identified by *selector* and *text*."""

	type: Literal['select_change']
	cssSelector: str
	selectedValue: str
	selectedText: str


class KeyPressDeterministicAction(RecorderBase):
	"""Parameters for pressing a key on an element identified by CSS selector."""

	type: Literal['key_press']
	cssSelector: str
	key: str


class NavigationAction(_BaseExtra):
	"""Parameters for navigating to a URL."""

	type: Literal['navigation']
	url: str


class ScrollDeterministicAction(_BaseExtra):
	"""Parameters for scrolling the page by x/y offsets (pixels)."""

	type: Literal['scroll']
	scrollX: int = 0
	scrollY: int = 0
	targetId: Optional[int] = None


class PageExtractionAction(_BaseExtra):
	"""Parameters for extracting content from the page."""

	type: Literal['extract_page_content']
	goal: str


# === SIMPLIFIED CLIPBOARD ACTIONS ===

class ClickToCopyAction(RecorderBase):
	"""Composite: click the element then capture page clipboard text."""

	type: Literal['click_to_copy']
	cssSelector: str
	timeoutMs: Optional[int] = Field(4000, description='Max time to wait for clipboard after click')


class ClipboardCopyAction(RecorderBase):
	"""Parameters for copying content to clipboard using pyperclip."""

	type: Literal['clipboard_copy']
	content: Optional[str] = Field(None, description='Content to copy to clipboard')
	cssSelector: Optional[str] = Field(None, description='Element selector to copy from (if applicable)')


class ClipboardPasteAction(RecorderBase):
	"""Parameters for pasting content from clipboard using pyperclip."""

	type: Literal['clipboard_paste']
	content: Optional[str] = Field(None, description='Content to paste (if None, uses current clipboard)')
	cssSelector: str = Field(..., description='Target element selector to paste into')


# TODO Temporary: Capture page clipboard text (navigator.clipboard.readText)
class ClipboardCaptureAction(_BaseExtra):
	"""Parameters for capturing current page clipboard text."""

	type: Literal['clipboard_capture']
	timeoutMs: Optional[int] = Field(5000, description='Max time to wait for non-empty clipboard text')
