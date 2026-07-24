package com.whatsplan.app;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Separates a WhatsApp group name from its sender without depending on one
 * specific WhatsApp notification layout. No message content enters the ID.
 */
public final class ConversationIdentityResolver {
    private static final Pattern SENDER_AT_GROUP =
            Pattern.compile("^(.{1,80}?)\\s+[@·]\\s+(.{1,120})$");
    private static final Pattern SENDER_IN_GROUP =
            Pattern.compile("^(.{1,80}?)\\s+\\((.{1,120})\\)$");

    public ConversationIdentity resolve(
            String packageName,
            String conversationTitle,
            String notificationTitle,
            String messageSender,
            String shortcutId,
            String notificationTag,
            boolean platformSaysGroup) {

        String conversation = clean(conversationTitle);
        String title = clean(notificationTitle);
        String sender = clean(messageSender);
        boolean group = platformSaysGroup;
        int confidence = 45;

        // Android MessagingStyle's conversation title is the strongest signal.
        if (!conversation.isBlank()) {
            group = true;
            confidence = 98;
        } else {
            Matcher at = SENDER_AT_GROUP.matcher(title);
            Matcher parens = SENDER_IN_GROUP.matcher(title);
            if (at.matches()) {
                if (sender.isBlank()) sender = clean(at.group(1));
                conversation = clean(at.group(2));
                group = true;
                confidence = 88;
            } else if (parens.matches()) {
                if (sender.isBlank()) sender = clean(parens.group(1));
                conversation = clean(parens.group(2));
                group = true;
                confidence = 82;
            } else if (group) {
                conversation = title;
                confidence = 75;
            }
        }

        if (sender.isBlank() && !group) sender = title;
        if (conversation.isBlank()) conversation = group ? title : sender;
        if (conversation.isBlank()) conversation = "WhatsApp";

        String stableBasis;
        if (!clean(shortcutId).isBlank()) {
            // Shortcut IDs are assigned per WhatsApp conversation and survive
            // notification text changes better than a visible title.
            stableBasis = packageName + "|shortcut|" + shortcutId;
            confidence = Math.max(confidence, 92);
        } else if (!conversation.equals("WhatsApp")) {
            stableBasis = packageName + "|name|" + normalize(conversation);
        } else {
            stableBasis = packageName + "|tag|" + clean(notificationTag);
        }

        return new ConversationIdentity(
                sha256(stableBasis), conversation, sender, group, confidence);
    }

    private String clean(String value) {
        return value == null ? "" : value.replace('\u200f', ' ')
                .replace('\u200e', ' ').replaceAll("\\s+", " ").trim();
    }

    private String normalize(String value) {
        return clean(value).toLowerCase(Locale.ROOT)
                .replaceAll("[^\\p{L}\\p{N}]+", " ").trim();
    }

    private String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder();
            for (int i = 0; i < 12; i++) {
                result.append(String.format(Locale.ROOT, "%02x", digest[i]));
            }
            return result.toString();
        } catch (Exception impossible) {
            return Integer.toHexString(value.hashCode());
        }
    }
}
