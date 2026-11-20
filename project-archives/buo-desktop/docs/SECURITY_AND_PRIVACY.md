# Buo — Security and Privacy Notes

Buo handles personal fitness information and may store profile details, workout history, recovery check-ins, journal entries, and training plans. Treat the local database and exported backups as private personal data.

- Never upload `buo.db`, exported user bundles, journal data, or local sync folders to a public repository.
- Never commit `cloud_config.json`. The uploaded configuration previously contained a Gemini API key; rotate/revoke that exposed key before enabling the integration again.
- Do not embed a real Gemini API key in an APK. Mobile application packages can be inspected. Use an authenticated server-side proxy for distributed builds.
- Configure Firebase Realtime Database rules to restrict reads/writes to the correct account. A URL plus an empty auth token is not a security policy.
- Keep Android release signing keys and passwords outside the repository.
- Review what data is exported or shared. Journal content and workout details should not be shared without the user's explicit action.
- Add a privacy policy, data deletion/export instructions, and a clear disclosure before any public distribution.
