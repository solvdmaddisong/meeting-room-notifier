# Setup Guide — Meeting Room Notifier

This walks you through everything from scratch. You'll need:
- Access to Google Cloud Console (free tier is fine)
- Google Workspace admin access (to enable domain-wide delegation)
- A GitHub account (free — GitHub Actions gives 2,000 free minutes/month)

---

## Part 1: Google Cloud Project

### 1.1 Create a project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown at the top left (next to "Google Cloud")
3. Click **New Project**
4. Name it something like `meeting-room-notifier`
5. Click **Create**
6. Make sure it's selected in the project dropdown

### 1.2 Enable the APIs

1. In the left sidebar, go to **APIs & Services > Library**
2. Search for **Google Calendar API** → click it → click **Enable**
3. Go back to the Library, search for **Gmail API** → click it → click **Enable**

---

## Part 2: Service Account

### 2.1 Create the service account

1. In the left sidebar, go to **IAM & Admin > Service Accounts**
2. Click **+ Create Service Account**
3. Name: `meeting-room-checker`
4. Click **Create and Continue**
5. Skip the optional role/access steps — just click **Done**

### 2.2 Create a key (JSON)

1. Click on the service account you just created
2. Go to the **Keys** tab
3. Click **Add Key > Create new key**
4. Select **JSON** → click **Create**
5. A `.json` file will download — **keep this safe, you'll need it later**

### 2.3 Enable domain-wide delegation

1. Still on the service account page, go to the **Details** tab
2. Expand **Advanced settings**
3. Copy the **Client ID** (a long number like `123456789012345678`)
4. Check the box **Enable Google Workspace Domain-wide Delegation**
   - If you don't see this option, you may need to enable it from the
     Workspace admin console instead (see next step)
5. Click **Save**

---

## Part 3: Google Workspace Admin Console

This step grants the service account permission to read calendars and send
emails on behalf of a user in your organisation.

1. Go to [admin.google.com](https://admin.google.com)
2. In the left sidebar: **Security > Access and data control > API controls**
3. Click **Manage Domain Wide Delegation**
4. Click **Add new**
5. **Client ID**: paste the Client ID from step 2.3
6. **OAuth scopes**: paste these two scopes (comma-separated):
   ```
   https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/gmail.send
   ```
7. Click **Authorise**

---

## Part 4: GitHub Repository

### 4.1 Create the repo

1. Go to [github.com/new](https://github.com/new)
2. Name it `meeting-room-notifier` (or anything you like)
3. Set it to **Private**
4. Click **Create repository**
5. Upload the project files:
   - `check_meetings.py`
   - `requirements.txt`
   - `.github/workflows/daily_check.yml`

   You can drag and drop files on the GitHub page, or use git:
   ```bash
   cd ~/Desktop/Meeting\ Room\ Project
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/meeting-room-notifier.git
   git push -u origin main
   ```

### 4.2 Add the secret

The service account JSON file needs to be stored as a base64-encoded secret.

1. Open Terminal and run:
   ```bash
   base64 -i ~/Downloads/meeting-room-checker-XXXXX.json | pbcopy
   ```
   (Replace the filename with your actual downloaded JSON file.
   This copies the base64 string to your clipboard.)

2. In your GitHub repo, go to **Settings > Secrets and variables > Actions**
3. Click **New repository secret**
4. Name: `GOOGLE_SA_CREDENTIALS_B64`
5. Value: paste from clipboard (Cmd+V)
6. Click **Add secret**

### 4.3 Add the variables

Still in **Settings > Secrets and variables > Actions**, click the
**Variables** tab, then add each of these:

| Variable name    | Value                                                              |
|------------------|--------------------------------------------------------------------|
| `CALENDAR_ID`    | `c_1882ntlpc6dt2g5ald7pe52suum54@resource.calendar.google.com`     |
| `MEETING_EMAIL`  | `meeting@solvdagency.com.au`                                       |
| `COMPANY_DOMAIN` | `solvdagency.com.au`                                               |
| `NOTIFY_EMAIL`   | `maddisong@solvdagency.com.au`                                     |
| `DELEGATE_EMAIL` | `maddisong@solvdagency.com.au`                                     |
| `TIMEZONE`       | `Australia/Sydney`                                                 |

> **Note:** `DELEGATE_EMAIL` is the Workspace user the service account
> impersonates. It needs to be someone who has access to the meeting room
> calendar and can send email. Your own account works fine.

---

## Part 5: Test It

### 5.1 Test manually from GitHub

1. In your repo, go to **Actions** tab
2. Click **Meeting Room Check** in the left sidebar
3. Click **Run workflow** (top right) → **Run workflow**
4. Watch the run — click into it to see logs
5. Check your inbox for the email

### 5.2 Test locally (optional)

```bash
cd ~/Desktop/Meeting\ Room\ Project

# Export the env vars (replace values as needed)
export GOOGLE_SA_CREDENTIALS_B64=$(base64 -i ~/Downloads/your-service-account.json)
export CALENDAR_ID="c_1882ntlpc6dt2g5ald7pe52suum54@resource.calendar.google.com"
export MEETING_EMAIL="meeting@solvdagency.com.au"
export COMPANY_DOMAIN="solvdagency.com.au"
export NOTIFY_EMAIL="maddisong@solvdagency.com.au"
export DELEGATE_EMAIL="maddisong@solvdagency.com.au"
export TIMEZONE="Australia/Sydney"

pip install -r requirements.txt
python check_meetings.py
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `403 Forbidden` on Calendar API | Make sure domain-wide delegation is set up (Part 3) and the scopes match exactly |
| `403` on Gmail send | Same as above — check the `gmail.send` scope is in the delegation |
| `401 Unauthorized` | Check the service account JSON is correct and base64-encoded properly |
| No email received | Check GitHub Actions logs — if the script says "No meeting room bookings today" there was nothing to report |
| Wrong time (1 hour off) | The cron is set for AEDT. During AEST (April-October) it will fire at 7:45am instead of 8:45am. You can change the cron to `45 22 * * 0-4` for AEST timing |

---

## Timing Note

GitHub Actions cron uses UTC. The workflow is set to `45 21 * * 0-4` which is:
- **8:45am AEDT** (daylight saving, Oct-Apr) — correct
- **7:45am AEST** (standard time, Apr-Oct) — 1 hour early

This is intentional — early is better than late for a morning briefing.
If you'd rather it be exact during AEST and 1 hour late during AEDT,
change the cron to `45 22 * * 0-4`.
