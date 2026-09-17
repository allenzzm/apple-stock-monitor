# Apple Stock Monitor — GitHub Actions

Runs an Apple Store pickup check every 5 minutes and sends a Discord webhook after every check.

## Default products

The script supports these 8 iPhone 18 Pro Max SKUs:

| Product | Part Number |
|---|---|
| Black 256GB | MJW44LL/A |
| Black 512GB | MJW84LL/A |
| Black 1TB | MJWD4LL/A |
| Black 2TB | MJWH4LL/A |
| Burgundy 256GB | MJW64LL/A |
| Burgundy 512GB | MJWA4LL/A |
| Burgundy 1TB | MJWF4LL/A |
| Burgundy 2TB | MJWK4LL/A |

## 1. Create a public repository

Create a new GitHub repository and set it to **Public**.

Upload this folder's contents so the repository contains:

```text
monitor.py
.github/workflows/monitor.yml
README.md
```

## 2. Add the Discord webhook as a GitHub Secret

In your repository:

**Settings → Secrets and variables → Actions → Secrets → New repository secret**

Create:

```text
Name: DISCORD_WEBHOOK
Value: https://discord.com/api/webhooks/...
```

Do NOT put the webhook URL directly in `monitor.py` or the workflow file.

## 3. Add ZIP_CODE as a repository variable

Go to:

**Settings → Secrets and variables → Actions → Variables → New repository variable**

Create:

```text
Name: ZIP_CODE
Value: 03079
```

## 4. Add PRODUCTS_TO_MONITOR as a repository variable

Create another repository variable:

```text
Name: PRODUCTS_TO_MONITOR
Value: Black 256GB,Burgundy 256GB
```

You can monitor any combination of the 8 supported names, separated by commas.

Examples:

```text
Black 256GB,Burgundy 256GB
```

```text
Black 256GB,Black 512GB,Black 1TB,Burgundy 256GB
```

```text
Black 256GB,Black 512GB,Black 1TB,Black 2TB,Burgundy 256GB,Burgundy 512GB,Burgundy 1TB,Burgundy 2TB
```

## 5. Enable GitHub Actions

Open the repository's **Actions** tab.

If GitHub asks you to enable workflows, enable them.

The workflow is scheduled for:

```text
*/5 * * * *
```

That means approximately every 5 minutes.

GitHub scheduled workflows can be delayed, especially during busy periods. Do not expect exact 5-minute execution.

## 6. Test it manually

Open:

**Actions → Apple Stock Monitor → Run workflow**

A Discord message should arrive after the run completes.

## Discord behavior

Every check sends one Discord summary.

If no stock exists, the message is a normal gray status update.

If stock is available, the message uses:
- `@everyone`
- `🚨 APPLE STOCK AVAILABLE`
- red embed
- store name
- pickup message/date
- distance

If you do not want `@everyone`, edit `monitor.py` and change:

```python
content = "@everyone 🚨 **APPLE STOCK AVAILABLE**"
```

to:

```python
content = "🚨 **APPLE STOCK AVAILABLE**"
```

## Important

Your Discord webhook must remain in GitHub Secrets.

Never commit the webhook URL into a public repository.
