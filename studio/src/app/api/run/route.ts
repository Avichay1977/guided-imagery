import Anthropic from "@anthropic-ai/sdk";
import { NextResponse } from "next/server";

import { getDevice } from "@/lib/devices/mix-notes";
import { buildSystemPrompt, buildUserPrompt } from "@/lib/engine";
import type { AutonomyLevel, ControlValues, RunResult } from "@/lib/types";

export const runtime = "nodejs";
export const maxDuration = 120;

const MODEL = "claude-opus-5";

interface RunRequestBody {
  deviceId: string;
  values: ControlValues;
  autonomy: AutonomyLevel;
  inputs: Record<string, string>;
}

export async function POST(request: Request) {
  if (!process.env.ANTHROPIC_API_KEY) {
    return NextResponse.json(
      {
        error:
          "המנוע לא מחובר. הגדר ANTHROPIC_API_KEY בקובץ .env.local והפעל מחדש את השרת.",
      },
      { status: 503 },
    );
  }

  let body: RunRequestBody;
  try {
    body = (await request.json()) as RunRequestBody;
  } catch {
    return NextResponse.json({ error: "בקשה לא תקינה." }, { status: 400 });
  }

  const device = getDevice(body.deviceId);
  if (!device) {
    return NextResponse.json({ error: "מכשיר לא נמצא." }, { status: 404 });
  }

  const missingRequired = device.inputs
    .filter((field) => field.required && !(body.inputs?.[field.id] ?? "").trim())
    .map((field) => field.label);

  if (missingRequired.length > 0) {
    return NextResponse.json(
      { error: `חסר קלט חובה: ${missingRequired.join(", ")}` },
      { status: 400 },
    );
  }

  const client = new Anthropic();
  const started = Date.now();

  try {
    const response = await client.beta.messages.create({
      model: MODEL,
      max_tokens: 16000,
      // ברירת המחדל ב־Opus 5 היא חשיבה אדפטיבית; effort שולט בעומק ובעלות.
      output_config: {
        effort: "medium",
        format: {
          type: "json_schema",
          schema: device.outputSchema,
        },
      },
      // מדיניות בטיחות עשויה לדחות בקשה; fallbacks מנתב אותה למודל חלופי
      // באותה קריאה במקום להחזיר סירוב.
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      system: buildSystemPrompt(device, body.values ?? {}, body.autonomy ?? device.autonomy),
      messages: [
        {
          role: "user",
          content: buildUserPrompt(device, body.inputs ?? {}),
        },
      ],
    });

    if (response.stop_reason === "refusal") {
      return NextResponse.json(
        {
          error:
            "המנוע סירב לעבד את הקלט הזה מטעמי מדיניות. נסה לנסח מחדש את ההערות.",
        },
        { status: 422 },
      );
    }

    if (response.stop_reason === "max_tokens") {
      return NextResponse.json(
        { error: "התשובה נקטעה. הקטן את הרזולוציה או קצר את ההערות." },
        { status: 502 },
      );
    }

    const text = response.content
      .filter((block) => block.type === "text")
      .map((block) => block.text)
      .join("");

    if (!text.trim()) {
      return NextResponse.json(
        { error: "המנוע לא החזיר תוכן." },
        { status: 502 },
      );
    }

    let parsed: Omit<RunResult, "meta">;
    try {
      parsed = JSON.parse(text) as Omit<RunResult, "meta">;
    } catch {
      return NextResponse.json(
        { error: "הפלט לא היה JSON תקין." },
        { status: 502 },
      );
    }

    const result: RunResult = {
      summary: parsed.summary ?? "",
      items: Array.isArray(parsed.items) ? parsed.items : [],
      missing: Array.isArray(parsed.missing) ? parsed.missing : [],
      meta: {
        model: response.model,
        inputTokens: response.usage.input_tokens,
        outputTokens: response.usage.output_tokens,
        ms: Date.now() - started,
      },
    };

    return NextResponse.json(result);
  } catch (error) {
    if (error instanceof Anthropic.RateLimitError) {
      return NextResponse.json(
        { error: "חריגה ממכסת הקריאות. נסה שוב בעוד רגע." },
        { status: 429 },
      );
    }
    if (error instanceof Anthropic.AuthenticationError) {
      return NextResponse.json(
        { error: "מפתח ה־API אינו תקין." },
        { status: 401 },
      );
    }
    if (error instanceof Anthropic.APIConnectionError) {
      return NextResponse.json(
        { error: "אין חיבור לשירות. בדוק את הרשת." },
        { status: 503 },
      );
    }
    if (error instanceof Anthropic.APIError) {
      return NextResponse.json(
        { error: `שגיאת מנוע (${error.status}): ${error.message}` },
        { status: 502 },
      );
    }
    return NextResponse.json({ error: "שגיאה לא צפויה בהרצה." }, { status: 500 });
  }
}
