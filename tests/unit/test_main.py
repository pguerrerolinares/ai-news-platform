"""Smoke tests for the CLI entry point (src/main.py).

Exercises import + main() with the DB layer and pipeline mocked out —
no real database connection or network access.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from src import main as main_module


class TestMain:
    async def test_returns_0_on_pipeline_success(self) -> None:
        with (
            patch.object(main_module, "init_db", new=AsyncMock()) as mock_init,
            patch.object(main_module, "close_db", new=AsyncMock()) as mock_close,
            patch.object(main_module, "get_session_factory") as mock_factory,
            patch.object(main_module, "run_pipeline", new=AsyncMock(return_value=True)),
            patch.object(main_module, "setup_logging"),
        ):
            session = AsyncMock()
            mock_factory.return_value.return_value.__aenter__.return_value = session
            mock_factory.return_value.return_value.__aexit__.return_value = False

            exit_code = await main_module.main()

        assert exit_code == 0
        mock_init.assert_awaited_once()
        mock_close.assert_awaited_once()

    async def test_returns_1_on_pipeline_failure(self) -> None:
        with (
            patch.object(main_module, "init_db", new=AsyncMock()),
            patch.object(main_module, "close_db", new=AsyncMock()) as mock_close,
            patch.object(main_module, "get_session_factory") as mock_factory,
            patch.object(main_module, "run_pipeline", new=AsyncMock(return_value=False)),
            patch.object(main_module, "setup_logging"),
        ):
            session = AsyncMock()
            mock_factory.return_value.return_value.__aenter__.return_value = session
            mock_factory.return_value.return_value.__aexit__.return_value = False

            exit_code = await main_module.main()

        assert exit_code == 1
        mock_close.assert_awaited_once()

    async def test_returns_1_and_closes_db_on_exception(self) -> None:
        """A failure anywhere in the pipeline must still release the DB (fail fast,
        no leaked connections) and report failure via exit code, not raise.
        """
        with (
            patch.object(main_module, "init_db", new=AsyncMock()),
            patch.object(main_module, "close_db", new=AsyncMock()) as mock_close,
            patch.object(main_module, "get_session_factory") as mock_factory,
            patch.object(
                main_module, "run_pipeline", new=AsyncMock(side_effect=RuntimeError("boom"))
            ),
            patch.object(main_module, "setup_logging"),
        ):
            session = AsyncMock()
            mock_factory.return_value.return_value.__aenter__.return_value = session
            mock_factory.return_value.return_value.__aexit__.return_value = False

            exit_code = await main_module.main()

        assert exit_code == 1
        mock_close.assert_awaited_once()
