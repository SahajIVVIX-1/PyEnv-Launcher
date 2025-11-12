import { GoogleGenAI } from "@google/genai";

declare global {
  interface ImportMetaEnv {
    readonly VITE_API_KEY?: string;
    [key: string]: string | undefined;
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }
}

// This is the correct way to access environment variables in Vite
const API_KEY = import.meta.env.VITE_API_KEY;

let ai: GoogleGenAI | null = null;

if (API_KEY) {
  ai = new GoogleGenAI({ apiKey: API_KEY });
} else {
  console.warn("VITE_API_KEY environment variable not set. Gemini API calls will fail.");
}

export const suggestCommitMessage = async (diff: string): Promise<string> => {
  if (!ai) {
    return "Dummy commit message: API key not configured.";
  }

  const prompt = `
    Based on the following git diff, suggest a concise and conventional commit message.
    The message should follow the Conventional Commits specification.
    Format: <type>[optional scope]: <description>
    
    Examples:
    - feat: allow provided config object to extend other configs
    - docs: correct spelling of CHANGELOG
    - fix(server): send cors headers for all requests
    
    Git Diff:
    ---
    ${diff}
    ---
  `;

  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: prompt,
    });

    return response.text.trim();
  } catch (error) {
    console.error("Error calling Gemini API:", error);
    throw new Error("Failed to get suggestion from Gemini API.");
  }
};
