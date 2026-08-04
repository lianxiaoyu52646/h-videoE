package com.videoenglish.app.novel;

/**
 * Fixed system prompt for on-device novel translation (Qwen Instruct).
 */
public final class NovelPrompt {
    private NovelPrompt() {}

    public static final String SYSTEM =
            "你是专业小说译者。只将英文小说段落译为流畅自然的中文。"
                    + "保留人名、地名、称谓、语气、叙事节奏与段落结构；"
                    + "不要解释、不要总结、不要加注释或前后缀；只输出译文本身。";

    /** ChatML-style prompt for Qwen2.5 Instruct. */
    public static String buildUserPrompt(String englishParagraph) {
        String en = englishParagraph == null ? "" : englishParagraph.trim();
        return "<|im_start|>system\n"
                + SYSTEM
                + "<|im_end|>\n"
                + "<|im_start|>user\n"
                + "请翻译以下小说段落：\n"
                + en
                + "<|im_end|>\n"
                + "<|im_start|>assistant\n";
    }

    public static String stripModelNoise(String raw) {
        if (raw == null) return "";
        String t = raw.trim();
        if (t.startsWith("```")) {
            int nl = t.indexOf('\n');
            if (nl > 0) t = t.substring(nl + 1);
            if (t.endsWith("```")) t = t.substring(0, t.length() - 3);
        }
        // Drop accidental role tags
        t = t.replace("<|im_end|>", "").replace("<|im_start|>assistant", "").trim();
        return t.trim();
    }
}
