# Persistent User Storage

## Overview
Your Flask app now uses **Azure-backed persistent storage** to ensure user data is never lost, even when the app restarts or is updated.

## How It Works

### 1. Storage Location
- User data is saved to the Azure `Users` table
- Profile rows use `RowKey = profile`
- The store persists between app restarts and deployments

### 2. Data Stored
For each user, the following information is permanently saved:
- **User ID** (Google/Facebook unique identifier)
- **Name** (from social login)
- **Email address**
- **Registration timestamp** (when they first signed up)
- **Admin status** (based on email address)

### 3. Automatic Operations
- **On App Startup**: Automatically loads existing users from Azure profiles
- **On User Registration**: Immediately saves new users to Azure
- **On User Login**: No data loss, existing users are preserved

## Benefits

### ✅ **Data Persistence**
- User information survives app restarts
- No data loss during updates or deployments
- Complete registration history preserved

### ✅ **Admin Access**
- All registered users visible in `/users` admin panel
- Registration dates tracked
- User growth metrics available

### ✅ **Reliability**
- Automatic file backup of user data
- Error handling for file operations
- Graceful fallback if file is corrupted

## File Structure

### Azure profile example
Each row is stored in the Azure `Users` table with `PartitionKey = user_id` and `RowKey = profile`.

## Testing

### Manual Test
Run the app and sign up or log in with a test account to verify Azure-backed storage works.

### What to Expect
1. **First Run**: Creates the Azure profile row on first signup
2. **User Signup**: Automatically adds users to Azure
3. **App Restart**: Loads all existing users from Azure on startup
4. **Admin Panel**: Shows all registered users with timestamps

## Security

### Data Protection
- Data is stored in Azure Table Storage
- Password hashes and verification state are persisted for auth recovery
- Only the fields needed by the app are saved

### Access Control
- Only admin users can view user list
- User data only accessible through authenticated routes
- No public access to user information

## Maintenance

### Backup
- Back up the Azure `Users` table if you need a copy of account data
- Local file backups are no longer used for user auth storage

### Monitoring
- App logs show user loading/saving operations
- Console messages indicate successful operations
- Error messages show if file operations fail

## Migration

If you had users before implementing persistent storage:
- Previous users should be present in Azure profiles
- No existing user data is lost if it was already synced to Azure
- New users are automatically added to Azure-backed storage

---

**Your user data is now fully persistent in Azure!** 🎉
