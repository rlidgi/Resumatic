# Admin AI Assistant Guide

This guide covers what the admin assistant on `/admin/stats` can do and gives example prompts you can submit.

## What It Can Do

The admin assistant is available on the admin stats page and can:

- summarize the current admin stats page
- inspect visit analytics and login summaries
- search registered users
- fetch detailed user context
- inspect recent feedback
- inspect subscription reconciliation data
- read data from the Azure `LoginAudit` table
- read data from the Azure `ResumeRevisions` table
- run controlled read-only Azure Table queries against `LoginAudit`
- run controlled read-only Azure Table queries against `ResumeRevisions`
- draft a single email
- send a single email when you explicitly tell it to send
- draft a targeted batch email
- send a targeted batch email when you explicitly tell it to send

## Important Limits

- It is read-only for data access.
- It does not delete or modify Azure table data.
- It only sends email when you explicitly instruct it to send.
- Batch email is capped and should be used with an explicit audience.
- Table querying uses Azure Table query semantics, not SQL.

## Best Prompting Style

You will usually get the best results if you:

- say exactly what table or data source you want checked
- mention the user email, user ID, company, or time range if relevant
- ask for a summary first, then ask for deeper drill-down
- explicitly say `draft` if you want email copy only
- explicitly say `send` if you want it to actually send

## Example Prompts

### General Admin Analysis

- `Summarize what stands out on the admin stats page right now.`
- `What looks unusual in current visits, conversions, or login activity?`
- `Give me the 3 most important operational takeaways from the current admin data.`
- `Explain what data sources you can access.`

### Users

- `Find user john@example.com and summarize their account activity.`
- `Show me users on trial with no recent login activity.`
- `Find users with high revision counts but no active subscription.`
- `Search for users with provider Google and summarize what you find.`

### Revisions And Applications

- `Inspect ResumeRevisions for user john@example.com and summarize recent activity.`
- `Show me recent revisions that mention Google in tracked applications.`
- `Find revision rows where follow_up_date is populated in applications.`
- `Look for users with many revisions but no applications tracked.`

### Login Audit

- `Inspect LoginAudit for john@example.com and summarize the most recent login history.`
- `Find login rows for this user ID: 12345 and tell me if anything looks unusual.`
- `Show me recent login audit rows from the last 7 days for users who later became active subscribers.`
- `Look for repeated login failures or strange patterns in LoginAudit.`

### Feedback

- `Summarize recent feedback submissions and group them by theme.`
- `Find negative feedback and tell me the main complaints.`
- `Look for comments mentioning pricing, bugs, or confusion.`

### Subscriptions

- `Summarize Stripe versus Azure reconciliation issues.`
- `Find subscription mismatches I should investigate first.`
- `Show me active subscribers with no recent product activity.`

## Query-Focused Prompts

The assistant can use controlled query tools for `LoginAudit` and `ResumeRevisions`. You do not need to write the raw filter yourself, but you can if you want.

### Natural-Language Query Requests

- `Query ResumeRevisions for rows belonging to user 12345 and return the latest 10.`
- `Query LoginAudit for rows where email is john@example.com.`
- `Look in ResumeRevisions for rows containing OpenAI in the stored data.`
- `Search LoginAudit for the latest rows for this user and show only a few key fields.`

### More Explicit Query Requests

- `Use a ResumeRevisions table query with a filter for PartitionKey eq '12345'.`
- `Query LoginAudit with select fields PartitionKey, RowKey, email, login_at.`
- `Run a LoginAudit query for the latest 20 rows for john@example.com.`

## Email Drafting Prompts

### Single Email Drafts

- `Draft an email to john@example.com asking them if they need help finishing their resume.`
- `Draft a short re-engagement email for a user who signed up but has not returned.`
- `Write a polite support follow-up email for a user who left negative feedback.`

### Targeted Batch Drafts

- `Find a good audience for a re-engagement email and draft the message.`
- `Identify users with high revision activity but no subscription and draft an upgrade email.`
- `Find inactive trial users and draft a reminder email for them.`

## Email Sending Prompts

Use explicit wording if you want the assistant to actually send.

### Single Send

- `Draft an email to john@example.com about their inactive account, then send it.`
- `Send this message to john@example.com with subject 'Need help with your resume?'`

### Batch Send

- `Find users with no login in 30 days but at least 3 revisions, draft a re-engagement email, show me the audience, and then send it.`
- `Create a targeted batch for inactive trial users, show me who would receive it, and send after confirmation.`

## Good Two-Step Workflow

For higher-stakes tasks, a two-step flow is best:

1. Ask for the audience or findings.
2. Ask for the draft.
3. Ask it to send only after you approve.

Example:

1. `Find users who started but did not return after signup.`
2. `Draft a short re-engagement email for that audience.`
3. `Send that batch now.`

## Manual Table Querying Outside The Assistant

You also have a manual script at:

- [scripts/query_table.py](C:/Users/rliog/Desktop/Resumatic_website2/scripts/query_table.py)

Example usage:

```powershell
python scripts/query_table.py ResumeRevisions --filter "PartitionKey eq 'USER_ID_HERE'" --top 10
```

```powershell
python scripts/query_table.py LoginAudit --filter "email eq 'user@example.com'" --select "PartitionKey,RowKey,login_at,email" --top 20
```

## Suggested First Prompts

If you are just getting started, try:

- `Explain what you can access and how you would use it.`
- `Summarize what stands out on the admin stats page right now.`
- `Find one useful audience for a targeted email campaign.`
- `Inspect ResumeRevisions and LoginAudit for one user and summarize their journey.`
