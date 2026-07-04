/**
 * Target languages for resume preview translation (Google Cloud Translation API codes).
 */
export type PreviewTranslateOption = {
    code: string;
    label: string;
};

/**
 * Select value for “no translation” (avoids empty-string options, which some browsers style poorly).
 * Not sent to the Translation API.
 */
export const PREVIEW_TRANSLATE_NONE_VALUE = '__source__';

/** Select value that resets the preview back to the original (English) resume data. */
export const PREVIEW_TRANSLATE_RESET_TO_ENGLISH_VALUE = '__reset_to_english__';

export const PREVIEW_TRANSLATE_OPTIONS: PreviewTranslateOption[] = [
    { code: PREVIEW_TRANSLATE_NONE_VALUE, label: 'Translate' },

    { code: PREVIEW_TRANSLATE_RESET_TO_ENGLISH_VALUE, label: 'English (default)' },

    { code: 'ar', label: 'Arabic' },
    { code: 'bn', label: 'Bengali' },
    { code: 'zh-CN', label: 'Chinese (Simplified)' },
    { code: 'fr', label: 'French' },
    { code: 'gu', label: 'Gujarati' },
    { code: 'hi', label: 'Hindi' },
    { code: 'kn', label: 'Kannada' },
    { code: 'ml', label: 'Malayalam' },
    { code: 'mr', label: 'Marathi' },
    { code: 'or', label: 'Odia' },
    { code: 'ps', label: 'Pashto' },
    { code: 'pa', label: 'Punjabi' },
    { code: 'sd', label: 'Sindhi' },
    { code: 'es', label: 'Spanish' },
    { code: 'ta', label: 'Tamil' },
    { code: 'te', label: 'Telugu' },
    { code: 'ur', label: 'Urdu' },
];
