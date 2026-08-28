package com.whatsplan.app;

public final class NotificationEnvelope {
    public final ConversationIdentity identity;
    public final String text;

    public NotificationEnvelope(ConversationIdentity identity, String text) {
        this.identity = identity;
        this.text = text;
    }
}
