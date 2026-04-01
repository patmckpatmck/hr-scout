import { readFile, writeFile } from "fs/promises";
import path from "path";

const HIST_PATH = path.join(process.cwd(), "public", "history.json");

async function readHistory() {
  try {
    const raw = await readFile(HIST_PATH, "utf-8");
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

// POST: toggle hitHR for a specific player on a specific date
export async function POST(request: Request) {
  const { date, playerName, hitHR } = await request.json();
  if (!date || !playerName || typeof hitHR !== "boolean") {
    return Response.json({ error: "Missing date, playerName, or hitHR" }, { status: 400 });
  }

  const history = await readHistory();
  const day = history.find((d: { date: string }) => d.date === date);
  if (!day) {
    return Response.json({ error: "Date not found" }, { status: 404 });
  }

  const player = day.players.find((p: { name: string }) => p.name === playerName);
  if (!player) {
    return Response.json({ error: "Player not found" }, { status: 404 });
  }

  player.hitHR = hitHR;
  await writeFile(HIST_PATH, JSON.stringify(history, null, 2));
  return Response.json({ ok: true });
}
