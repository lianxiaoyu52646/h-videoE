package com.videoenglish.app.novel;

/**
 * Fixed system prompt for on-device novel translation (Qwen Instruct).
 */
public final class NovelPrompt {
    private NovelPrompt() {}

    public static final String SYSTEM =
            "你是专业的英文→中文小说翻译专家。只翻译小说正文，输出流畅自然的中文译文。"
                    + "严格遵守："
                    + "1. 只输出译文，不要解释、总结、注释、前后缀或礼貌语；"
                    + "2. 保留人名、地名、称谓、标点语气与段落结构；"
                    + "3. 保持叙事节奏与文学风格，勿改写成口语聊天；"
                    + "4. 不要翻译或改写本不存在的内容。";

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
        t = t.replace("<|im_end|>", "").replace("<|im_start|>assistant", "").trim();
        return t.trim();
    }
}
