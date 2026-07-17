from app.config import settings


def test_static_dir_points_to_existing_app_static_folder() -> None:
    assert settings.static_dir.exists(), "static_dir should resolve to an existing directory"
    assert (settings.static_dir / "index.html").exists(), "index.html should be available in static_dir"
