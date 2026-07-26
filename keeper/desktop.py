from __future__ import annotations

import argparse
import json
import threading
from pathlib import Path
from typing import Any, Callable

from keeper.app.service import KeeperApplication


class KeeperViewModel:
    def __init__(self, application: KeeperApplication) -> None:
        self.application = application

    def dashboard(self) -> dict[str, Any]:
        return self.application.dashboard()

    def add_project(self, path: str) -> dict[str, Any]:
        return self.application.add_project(Path(path))

    def create_task(self, values: dict[str, Any]) -> dict[str, Any]:
        return self.application.create_task(values)

    def run_demo(self) -> dict[str, Any]:
        return self.application.run_mock_demo()

    def diagnostics(self) -> dict[str, Any]:
        return self.application.diagnostics()

    def complete_setup(self, evidence_directory: str | None = None) -> None:
        self.application.finish_setup(
            Path(evidence_directory) if evidence_directory else None
        )

    def create_authorization(self, values: dict[str, Any]) -> dict[str, Any]:
        return self.application.create_authorization(
            str(values["capability"]),
            str(values["task_id"]),
            str(values["repository"]),
            str(values["approving_authority"]),
            int(values["minutes"]),
            bool(values.get("reusable", False)),
        )


class KeeperDesktop:
    COLORS = {
        "black": "#0B0B0B",
        "gold": "#D4AF37",
        "gray": "#272727",
        "white": "#F5F5F5",
        "muted": "#B7B7B7",
    }

    def __init__(self, application: KeeperApplication) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.application = application
        self.view_model = KeeperViewModel(application)
        self.root = tk.Tk()
        self.root.title("Keeper")
        self.root.geometry("1180x760")
        self.root.minsize(900, 600)
        self._configure_style()
        self.status = tk.StringVar(value="Ready")
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=12)
        self._build_dashboard()
        self._build_projects()
        self._build_tasks()
        self._build_workflow()
        self._build_findings()
        self._build_authorizations()
        self._build_history()
        self._build_settings()
        ttk.Label(self.root, textvariable=self.status, anchor="w").pack(
            fill="x", padx=12, pady=(0, 8)
        )
        if not application.setup_complete():
            self.root.after(100, self._first_run)
        self.refresh()

    def run(self) -> None:
        self.root.mainloop()

    def _configure_style(self) -> None:
        style = self.ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", background=self.COLORS["black"], foreground=self.COLORS["white"])
        style.configure("TFrame", background=self.COLORS["black"])
        style.configure("TLabel", background=self.COLORS["black"], foreground=self.COLORS["white"])
        style.configure("TButton", background=self.COLORS["gold"], foreground=self.COLORS["black"])
        style.configure("Treeview", background=self.COLORS["gray"], foreground=self.COLORS["white"], fieldbackground=self.COLORS["gray"])
        style.configure("TNotebook", background=self.COLORS["black"])
        style.configure("TNotebook.Tab", background=self.COLORS["gray"], foreground=self.COLORS["white"])
        style.map("TNotebook.Tab", background=[("selected", self.COLORS["gold"])], foreground=[("selected", self.COLORS["black"])])
        self.root.configure(background=self.COLORS["black"])

    def _tab(self, title: str) -> Any:
        frame = self.ttk.Frame(self.notebook)
        self.notebook.add(frame, text=title)
        return frame

    def _build_dashboard(self) -> None:
        frame = self._tab("Home")
        self.dashboard_text = self.tk.Text(
            frame, bg=self.COLORS["gray"], fg=self.COLORS["white"], wrap="word"
        )
        self.dashboard_text.pack(fill="both", expand=True, padx=8, pady=8)
        buttons = self.ttk.Frame(frame)
        buttons.pack(fill="x", padx=8, pady=8)
        self.ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side="left")
        self.ttk.Button(buttons, text="Run safe mock demonstration", command=self._run_demo).pack(side="left", padx=8)

    def _build_projects(self) -> None:
        frame = self._tab("Projects")
        self.project_path = self.tk.StringVar()
        self.ttk.Label(frame, text="Existing Git repository").pack(anchor="w", padx=8, pady=(8, 2))
        self.ttk.Entry(frame, textvariable=self.project_path).pack(fill="x", padx=8)
        self.ttk.Button(frame, text="Add and inspect repository", command=self._add_project).pack(anchor="w", padx=8, pady=8)
        self.projects_text = self.tk.Text(frame, bg=self.COLORS["gray"], fg=self.COLORS["white"])
        self.projects_text.pack(fill="both", expand=True, padx=8, pady=8)

    def _build_tasks(self) -> None:
        frame = self._tab("Tasks")
        self.task_fields: dict[str, Any] = {}
        for label, key in (
            ("Title", "title"),
            ("Objective", "objective"),
            ("Included paths (comma-separated)", "included_paths"),
            ("Excluded paths", "excluded_paths"),
            ("Baseline commit", "baseline"),
            ("Target branch", "target_branch"),
            ("Risk", "risk"),
            ("Allowed actions", "allowed_actions"),
            ("Prohibited actions", "prohibited_actions"),
            ("Required validations", "required_validations"),
            ("Required reviewers", "required_reviewers"),
            ("Completion criteria", "completion_criteria"),
        ):
            self.ttk.Label(frame, text=label).pack(anchor="w", padx=8, pady=(5, 0))
            variable = self.tk.StringVar()
            self.task_fields[key] = variable
            self.ttk.Entry(frame, textvariable=variable).pack(fill="x", padx=8)
        self.ttk.Button(frame, text="Save task", command=self._create_task).pack(anchor="w", padx=8, pady=8)

    def _build_workflow(self) -> None:
        frame = self._tab("Workflow")
        self.workflow_text = self._readonly_text(frame)
        self._set_text(self.workflow_text, "No workflow is running.\nPause, resume, cancel, logs, retries, stages and artifacts appear here.")

    def _build_findings(self) -> None:
        frame = self._tab("Findings")
        self.findings_text = self._readonly_text(frame)
        self._set_text(self.findings_text, "No unresolved findings.")

    def _build_authorizations(self) -> None:
        frame = self._tab("Authorizations")
        form = self.ttk.Frame(frame)
        form.pack(fill="x", padx=8, pady=8)
        self.authorization_fields: dict[str, Any] = {}
        for label, key, default in (
            ("Action (commit/push/network)", "capability", "commit"),
            ("Task ID", "task_id", ""),
            ("Exact repository", "repository", ""),
            ("Approving user", "approving_authority", ""),
            ("Expires in minutes", "minutes", "15"),
        ):
            self.ttk.Label(form, text=label).pack(anchor="w")
            variable = self.tk.StringVar(value=default)
            self.authorization_fields[key] = variable
            self.ttk.Entry(form, textvariable=variable).pack(fill="x")
        self.ttk.Button(
            form, text="Grant scoped one-time authorization", command=self._authorize
        ).pack(anchor="w", pady=8)
        self.authorization_text = self._readonly_text(frame)
        self._set_text(self.authorization_text, "No pending authorization.")

    def _build_history(self) -> None:
        frame = self._tab("History & Evidence")
        self.history_text = self._readonly_text(frame)
        self._set_text(self.history_text, "Run history is empty.")

    def _build_settings(self) -> None:
        frame = self._tab("Settings")
        diagnostics = json.dumps(self.application.diagnostics(), indent=2)
        self.settings_text = self._readonly_text(frame)
        self._set_text(self.settings_text, diagnostics)

    def _readonly_text(self, frame: Any) -> Any:
        widget = self.tk.Text(frame, bg=self.COLORS["gray"], fg=self.COLORS["white"], wrap="word")
        widget.pack(fill="both", expand=True, padx=8, pady=8)
        return widget

    def refresh(self) -> None:
        dashboard = self.view_model.dashboard()
        self._set_text(self.dashboard_text, json.dumps(dashboard, indent=2))
        self._set_text(self.projects_text, json.dumps(self.application.projects(), indent=2))
        self._set_text(self.history_text, json.dumps(self.application.store.list("runs"), indent=2))
        self._set_text(self.authorization_text, json.dumps(self.application.store.list("authorizations"), indent=2))
        self._set_text(self.findings_text, json.dumps(self.application.store.list("findings"), indent=2))

    def _first_run(self) -> None:
        diagnostics = self.application.diagnostics()
        wizard = self.tk.Toplevel(self.root)
        wizard.title("Keeper first-run setup")
        wizard.geometry("680x520")
        wizard.transient(self.root)
        wizard.grab_set()
        body = self.tk.Text(
            wizard, bg=self.COLORS["gray"], fg=self.COLORS["white"], wrap="word"
        )
        body.pack(fill="both", expand=True, padx=12, pady=12)
        provider_lines = "\n".join(
            f"- {item['display_name']}: "
            f"{'available' if item['available'] else 'optional / unavailable'}"
            for item in diagnostics["providers"]
        )
        body.insert(
            "1.0",
            "Welcome to Keeper\n\n"
            "Keeper coordinates controlled local development workflows. It cannot "
            "merge, force-push, deploy, trade, spend money, or delete repositories, "
            "branches, or worktrees.\n\n"
            f"Git: {'available' if diagnostics['git_available'] else 'missing'}\n"
            f"Python: {diagnostics['python']}\n"
            f"Writable data directory: {diagnostics['data_directory_writable']}\n\n"
            f"Providers\n{provider_lines}\n\n"
            "The deterministic mock provider is always available. After setup, add "
            "the first repository in Projects and optionally run the safe demonstration.",
        )
        body.configure(state="disabled")

        def finish() -> None:
            self.application.finish_setup()
            wizard.destroy()
            self.status.set(
                "First-run setup completed. Add a repository or run the mock demonstration."
            )
            self.refresh()

        self.ttk.Button(wizard, text="Complete safe setup", command=finish).pack(
            pady=(0, 12)
        )

    def _add_project(self) -> None:
        self._handle(lambda: self.view_model.add_project(self.project_path.get()), "Repository added")

    def _create_task(self) -> None:
        values = {key: variable.get() for key, variable in self.task_fields.items()}
        for key in (
            "included_paths",
            "excluded_paths",
            "allowed_actions",
            "prohibited_actions",
            "required_validations",
            "required_reviewers",
            "completion_criteria",
        ):
            values[key] = [item.strip() for item in str(values[key]).split(",") if item.strip()]
        self._handle(lambda: self.view_model.create_task(values), "Task saved")

    def _authorize(self) -> None:
        values = {key: variable.get() for key, variable in self.authorization_fields.items()}
        self._handle(
            lambda: self.view_model.create_authorization(values),
            "Scoped authorization recorded",
        )

    def _run_demo(self) -> None:
        self.status.set("Running deterministic mock workflow…")

        def work() -> None:
            try:
                result = self.view_model.run_demo()
                self.root.after(0, lambda: self._complete_async(f"Mock workflow: {result['status']}"))
            except Exception as error:
                self.root.after(0, lambda: self._show_error(str(error)))

        threading.Thread(target=work, daemon=True).start()

    def _handle(self, operation: Callable[[], Any], success: str) -> None:
        try:
            operation()
            self.status.set(success)
            self.refresh()
        except Exception as error:
            self._show_error(str(error))

    def _complete_async(self, message: str) -> None:
        self.status.set(message)
        self.refresh()

    def _show_error(self, message: str) -> None:
        from tkinter import messagebox

        self.status.set("Operation failed")
        messagebox.showerror("Keeper", message)

    @staticmethod
    def _set_text(widget: Any, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Keeper local desktop application")
    result.add_argument("--data-dir", type=Path)
    result.add_argument("--diagnostics", action="store_true")
    result.add_argument("--mock-demo", action="store_true")
    return result


def main(arguments: list[str] | None = None) -> int:
    options = parser().parse_args(arguments)
    application = KeeperApplication(options.data_dir)
    if options.diagnostics:
        print(json.dumps(application.diagnostics(), indent=2))
        return 0
    if options.mock_demo:
        print(json.dumps(application.run_mock_demo(), indent=2))
        return 0
    KeeperDesktop(application).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
