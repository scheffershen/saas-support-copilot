-- Sample rows for Loopline. Matches sample_app/loopline/app/seed.py (used for the
-- SQLite quickstart); this .sql version is for the MySQL setup in Episode 16.

INSERT INTO users (id, name, email, role, is_active) VALUES
  (1, 'Amara Diallo', 'amara@loopline.example', 'support_agent', 1),
  (2, 'Priya Nair', 'priya@loopline.example', 'support_lead', 1),
  (3, 'Tom Reyes', 'tom@loopline.example', 'support_agent', 0),
  (4, 'Jonas Weber', 'jonas@loopline.example', 'billing_admin', 1),
  (5, 'New Hire', 'new.hire@loopline.example', 'support_agent', 1);

-- user_id 5 has no row here on purpose - see app/notifications.py
INSERT INTO notification_settings (user_id, notify_on_comment, notify_on_status_change) VALUES
  (1, 1, 1),
  (2, 1, 0),
  (4, 1, 1);

INSERT INTO tickets (id, title, description, status, requester_id, assignee_id) VALUES
  (1, 'Cannot reset password', 'Reset link expires immediately.', 'open', 4, 1),
  (2, 'Export button does nothing', 'Clicking Export on the tickets list does not download a file.', 'in_progress', 2, 1),
  (3, 'Add dark mode', 'Several users asked for a dark theme.', 'open', 4, NULL),
  (4, 'Slow ticket list on large accounts', 'List view takes 8s+ to load past ~2000 tickets.', 'open', 2, 5);

INSERT INTO comments (ticket_id, author_id, body) VALUES
  (1, 1, 'Looking into the expiry bug on the reset link now.'),
  (2, 1, 'Confirmed - export handler is returning 500.'),
  (4, 2, 'Reproduced locally, seems like a missing index.');
