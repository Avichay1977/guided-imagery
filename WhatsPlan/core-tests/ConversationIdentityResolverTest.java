import com.whatsplan.app.ConversationIdentity;
import com.whatsplan.app.ConversationIdentityResolver;

public final class ConversationIdentityResolverTest {
    public static void main(String[] args) {
        ConversationIdentityResolver resolver = new ConversationIdentityResolver();

        ConversationIdentity nativeGroup = resolver.resolve(
                "com.whatsapp", "Oy Division", "אבי", "אבי",
                "wa_group_123", "tag", true);
        require(nativeGroup.group, "native MessagingStyle group not detected");
        require(nativeGroup.name.equals("Oy Division"), "conversation title lost");
        require(nativeGroup.sender.equals("אבי"), "sender lost");

        ConversationIdentity titleFallback = resolver.resolve(
                "com.whatsapp", "", "אבי @ Freud Delay Team", "",
                "", "tag2", false);
        require(titleFallback.group, "title fallback group not detected");
        require(titleFallback.name.equals("Freud Delay Team"), "fallback group wrong");
        require(titleFallback.sender.equals("אבי"), "fallback sender wrong");

        ConversationIdentity privateChat = resolver.resolve(
                "com.whatsapp", "", "נועם", "", "private_noam", "tag3", false);
        require(!privateChat.group, "private chat classified as group");
        require(privateChat.sender.equals("נועם"), "private sender wrong");

        ConversationIdentity sameShortcutRenamed = resolver.resolve(
                "com.whatsapp", "Oy Division New", "רון", "רון",
                "wa_group_123", "changed", true);
        require(nativeGroup.id.equals(sameShortcutRenamed.id),
                "group rename must retain stable shortcut-based ID");

        System.out.println("Conversation identity tests passed");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
