package com.whatsplan.app;

public final class ConversationIdentity {
    public final String id;
    public final String name;
    public final String sender;
    public final boolean group;
    public final int confidence;

    public ConversationIdentity(String id, String name, String sender,
                                boolean group, int confidence) {
        this.id = id;
        this.name = name;
        this.sender = sender;
        this.group = group;
        this.confidence = confidence;
    }
}
