import threading


class Worker:
    """Exactly one durable queue consumer per local application instance."""

    def __init__(self, db, handlers):
        self.db, self.handlers = db, handlers
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.db.recover()
        self.thread = threading.Thread(target=self.loop, name="voicetrail-worker", daemon=True)
        self.thread.start()

    def loop(self):
        while not self.stop_event.is_set():
            job = self.db.one("SELECT * FROM job WHERE status='queued' "
                              "ORDER BY CASE WHEN kind='model' THEN 0 ELSE 1 END,created LIMIT 1")
            if not job:
                self.stop_event.wait(.25)
                continue
            if job["cancel_requested"]:
                self.db.execute("UPDATE job SET status='cancelled' WHERE id=?", (job["id"],))
                continue
            try:
                self.db.execute("UPDATE job SET status='running' WHERE id=?", (job["id"],))
                self.handlers[job["kind"]](job["id"])
            except Exception as exc:
                self.db.execute("UPDATE job SET status='failed',error=? WHERE id=?",
                                (f"Processing failed ({type(exc).__name__}); retry or check inputs.",
                                 job["id"]))

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
