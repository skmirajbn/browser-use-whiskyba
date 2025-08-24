"""About:blank watchdog for managing about:blank tabs with Vector AI Agent loading screen."""

from typing import TYPE_CHECKING, ClassVar

from bubus import BaseEvent
from cdp_use.cdp.target import TargetID
from pydantic import PrivateAttr

from browser_use.browser.events import (
	AboutBlankDVDScreensaverShownEvent,
	BrowserStopEvent,
	BrowserStoppedEvent,
	CloseTabEvent,
	NavigateToUrlEvent,
	TabClosedEvent,
	TabCreatedEvent,
)
from browser_use.browser.watchdog_base import BaseWatchdog

if TYPE_CHECKING:
	pass


class AboutBlankWatchdog(BaseWatchdog):
	"""Ensures there's always exactly one about:blank tab with Vector AI Agent loading screen."""

	# Event contracts
	LISTENS_TO: ClassVar[list[type[BaseEvent]]] = [
		BrowserStopEvent,
		BrowserStoppedEvent,
		TabCreatedEvent,
		TabClosedEvent,
	]
	EMITS: ClassVar[list[type[BaseEvent]]] = [
		NavigateToUrlEvent,
		CloseTabEvent,
		AboutBlankDVDScreensaverShownEvent,
	]

	_stopping: bool = PrivateAttr(default=False)

	async def on_BrowserStopEvent(self, event: BrowserStopEvent) -> None:
		"""Handle browser stop request - stop creating new tabs."""
		# logger.info('[AboutBlankWatchdog] Browser stop requested, stopping tab creation')
		self._stopping = True

	async def on_BrowserStoppedEvent(self, event: BrowserStoppedEvent) -> None:
		"""Handle browser stopped event."""
		# logger.info('[AboutBlankWatchdog] Browser stopped')
		self._stopping = True

	async def on_TabCreatedEvent(self, event: TabCreatedEvent) -> None:
		"""Check tabs when a new tab is created."""
		# logger.debug(f'[AboutBlankWatchdog] ➕ New tab created: {event.url}')

		# If an about:blank tab was created, show Vector AI Agent loading screen on all about:blank tabs
		if event.url == 'about:blank':
			await self._show_dvd_screensaver_on_about_blank_tabs()

	async def on_TabClosedEvent(self, event: TabClosedEvent) -> None:
		"""Check tabs when a tab is closed and proactively create about:blank if needed."""
		# logger.debug('[AboutBlankWatchdog] Tab closing, checking if we need to create about:blank tab')

		# Don't create new tabs if browser is shutting down
		if self._stopping:
			# logger.debug('[AboutBlankWatchdog] Browser is stopping, not creating new tabs')
			return

		# Check if we're about to close the last tab (event happens BEFORE tab closes)
		# Use _cdp_get_all_pages for quick check without fetching titles
		page_targets = await self.browser_session._cdp_get_all_pages()
		if len(page_targets) <= 1:
			self.logger.debug(
				'[AboutBlankWatchdog] Last tab closing, creating new about:blank tab to avoid closing entire browser'
			)
			# Create the animation tab since no tabs should remain
			navigate_event = self.event_bus.dispatch(NavigateToUrlEvent(url='about:blank', new_tab=True))
			await navigate_event
			# Show Vector AI Agent loading screen on the new tab
			await self._show_dvd_screensaver_on_about_blank_tabs()
		else:
			# Multiple tabs exist, check after close
			await self._check_and_ensure_about_blank_tab()

	async def attach_to_target(self, target_id: TargetID) -> None:
		"""AboutBlankWatchdog doesn't monitor individual targets."""
		pass

	async def _check_and_ensure_about_blank_tab(self) -> None:
		"""Check current tabs and ensure exactly one about:blank tab with animation exists."""
		try:
			# For quick checks, just get page targets without titles to reduce noise
			page_targets = await self.browser_session._cdp_get_all_pages()

			# If no tabs exist at all, create one to keep browser alive
			if len(page_targets) == 0:
				# Only create a new tab if there are no tabs at all
				self.logger.debug('[AboutBlankWatchdog] No tabs exist, creating new about:blank Vector AI Agent loading screen tab')
				navigate_event = self.event_bus.dispatch(NavigateToUrlEvent(url='about:blank', new_tab=True))
				await navigate_event
				# Show Vector AI Agent loading screen on the new tab
				await self._show_dvd_screensaver_on_about_blank_tabs()
			# Otherwise there are tabs, don't create new ones to avoid interfering

		except Exception as e:
			self.logger.error(f'[AboutBlankWatchdog] Error ensuring about:blank tab: {e}')

	async def _show_dvd_screensaver_on_about_blank_tabs(self) -> None:
		"""Show Vector AI Agent loading screen on all about:blank pages only."""
		try:
			# Get just the page targets without expensive title fetching
			page_targets = await self.browser_session._cdp_get_all_pages()
			browser_session_label = str(self.browser_session.id)[-4:]

			for page_target in page_targets:
				target_id = page_target['targetId']
				url = page_target['url']

				# Only target about:blank pages specifically
				if url == 'about:blank':
					await self._show_dvd_screensaver_loading_animation_cdp(target_id, browser_session_label)

		except Exception as e:
			self.logger.error(f'[AboutBlankWatchdog] Error showing Vector AI Agent loading screen: {e}')

	async def _show_dvd_screensaver_loading_animation_cdp(self, target_id: TargetID, browser_session_label: str) -> None:
		"""
		Injects a Vector AI Agent loading screen overlay into the target using CDP.
		This is used to visually indicate that the browser is setting up or waiting.
		"""
		try:
			# Create temporary session for this target without switching focus
			temp_session = await self.browser_session.get_or_create_cdp_session(target_id, focus=False)

			# Inject the Vector AI Agent loading screen script
			script = f"""
				(function(browser_session_label) {{
					// Idempotency check
					if (window.__vectoraiAnimationRunning) {{
						return; // Already running, don't add another
					}}
					window.__vectoraiAnimationRunning = true;
					
					// Ensure document.body exists before proceeding
					if (!document.body) {{
						// Try again after DOM is ready
						window.__vectoraiAnimationRunning = false; // Reset flag to retry
						if (document.readyState === 'loading') {{
							document.addEventListener('DOMContentLoaded', () => arguments.callee(browser_session_label));
						}}
						return;
					}}
					
					const loading_title = `Starting Vector AI Agent ${{browser_session_label}}...`;
					if (document.title === loading_title) {{
						return;      // already run on this tab, dont run again
					}}
					document.title = loading_title;

					// Create the main overlay
					const loadingOverlay = document.createElement('div');
					loadingOverlay.id = 'vectorai-loading-screen';
					loadingOverlay.style.position = 'fixed';
					loadingOverlay.style.top = '0';
					loadingOverlay.style.left = '0';
					loadingOverlay.style.width = '100vw';
					loadingOverlay.style.height = '100vh';
					loadingOverlay.style.background = 'linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%)';
					loadingOverlay.style.zIndex = '99999';
					loadingOverlay.style.display = 'flex';
					loadingOverlay.style.flexDirection = 'column';
					loadingOverlay.style.justifyContent = 'center';
					loadingOverlay.style.alignItems = 'center';
					loadingOverlay.style.fontFamily = 'system-ui, -apple-system, sans-serif';

					// Create the main title
					const title = document.createElement('h1');
					title.textContent = 'Vector AI Agent';
					title.style.fontSize = '4rem';
					title.style.fontWeight = '700';
					title.style.color = '#ffffff';
					title.style.margin = '0 0 1rem 0';
					title.style.textShadow = '0 4px 8px rgba(0,0,0,0.5)';
					title.style.letterSpacing = '0.1em';

					// Create the subtitle
					const subtitle = document.createElement('p');
					subtitle.textContent = 'Browser Automation Agent';
					subtitle.style.fontSize = '1.2rem';
					subtitle.style.color = '#cccccc';
					subtitle.style.margin = '0 0 2rem 0';
					subtitle.style.fontWeight = '300';

					// Create the status text
					const status = document.createElement('p');
					status.textContent = `Starting agent ${{browser_session_label}}...`;
					status.style.fontSize = '1rem';
					status.style.color = '#999999';
					status.style.margin = '0';
					status.style.fontWeight = '400';

					// Add elements to overlay
					loadingOverlay.appendChild(title);
					loadingOverlay.appendChild(subtitle);
					loadingOverlay.appendChild(status);
					document.body.appendChild(loadingOverlay);

					// Add CSS for better styling
					const style = document.createElement('style');
					style.innerHTML = `
						#vectorai-loading-screen {{
							user-select: none;
							pointer-events: none;
						}}
						#vectorai-loading-screen * {{
							user-select: none;
							pointer-events: none;
						}}
					`;
					document.head.appendChild(style);
				}})('{browser_session_label}');
			"""

			await temp_session.cdp_client.send.Runtime.evaluate(params={'expression': script}, session_id=temp_session.session_id)

			# No need to detach - session is cached

			# Dispatch event
			self.event_bus.dispatch(AboutBlankDVDScreensaverShownEvent(target_id=target_id))

		except Exception as e:
			self.logger.error(f'[AboutBlankWatchdog] Error injecting Vector AI Agent loading screen: {e}')
