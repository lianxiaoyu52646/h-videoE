#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::io;
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::{AppHandle, Manager};

struct BackendState(Mutex<Option<Child>>);

fn desktop_host() -> String {
    env::var("DESKTOP_HOST").unwrap_or_else(|_| "127.0.0.1".into())
}

fn desktop_port() -> u16 {
    env::var("DESKTOP_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(18555)
}

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("..")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from("."))
}

fn release_sidecar_path(app: &AppHandle) -> io::Result<PathBuf> {
    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|err| io::Error::new(io::ErrorKind::NotFound, err.to_string()))?;
    let binary_name = if cfg!(target_os = "windows") {
        "videoenglish-backend.exe"
    } else {
        "videoenglish-backend"
    };
    let candidates = [
        resource_dir.join("sidecar").join("videoenglish-backend").join(binary_name),
        resource_dir.join("videoenglish-backend").join(binary_name),
        resource_dir.join(binary_name),
    ];
    for candidate in candidates {
        if candidate.exists() {
            return Ok(candidate);
        }
    }
    Err(io::Error::new(
        io::ErrorKind::NotFound,
        "packaged backend sidecar was not found in resources",
    ))
}

fn spawn_backend(app: &AppHandle) -> io::Result<Child> {
    let host = desktop_host();
    let port = desktop_port().to_string();

    let mut command = if cfg!(debug_assertions) {
        let python = env::var("VIDEOENGLISH_PYTHON").unwrap_or_else(|_| "python".into());
        let mut cmd = Command::new(python);
        cmd.arg("-m").arg("app.desktop_runtime");
        cmd.current_dir(repo_root());
        cmd
    } else {
        Command::new(release_sidecar_path(app)?)
    };

    command
        .env("APP_MODE", "desktop")
        .env("LOCAL_AUTO_USER", "1")
        .env("INLINE_WORKER", if cfg!(debug_assertions) { "1" } else { "0" })
        .env("DESKTOP_HOT_RELOAD", if cfg!(debug_assertions) { "1" } else { "0" })
        .env("DESKTOP_HOST", host)
        .env("DESKTOP_PORT", port)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
}

fn wait_for_backend(host: &str, port: u16, timeout: Duration) -> io::Result<()> {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if TcpStream::connect((host, port)).is_ok() {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(250));
    }
    Err(io::Error::new(
        io::ErrorKind::TimedOut,
        "backend did not become ready before timeout",
    ))
}

fn main() {
    let app = tauri::Builder::default()
        .setup(|app| {
            let child = spawn_backend(&app.handle())?;
            wait_for_backend(&desktop_host(), desktop_port(), Duration::from_secs(15))?;
            app.manage(BackendState(Mutex::new(Some(child))));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build desktop shell");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            if let Some(state) = app_handle.try_state::<BackendState>() {
                if let Some(mut child) = state.0.lock().ok().and_then(|mut guard| guard.take()) {
                    let _ = child.kill();
                }
            }
        }
    });
}
