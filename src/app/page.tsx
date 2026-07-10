import { readFile } from "fs/promises";
import path from "path";
import HRScout from "./HRScout";

export const dynamic = "force-dynamic"; // always re-read file on each request

export default async function Page() {
  let data = null;
  let history = null;
  let calibration = null;
  try {
    const filePath = path.join(process.cwd(), "public", "data.json");
    const raw = await readFile(filePath, "utf-8");
    data = JSON.parse(raw);
  } catch {
    // data.json doesn't exist yet — script hasn't run
  }
  try {
    const histPath = path.join(process.cwd(), "public", "history.json");
    const raw = await readFile(histPath, "utf-8");
    history = JSON.parse(raw);
  } catch {
    // history.json doesn't exist yet
  }
  try {
    const calibPath = path.join(process.cwd(), "public", "calibration.json");
    const raw = await readFile(calibPath, "utf-8");
    calibration = JSON.parse(raw);
  } catch {
    // calibration.json doesn't exist yet — probabilities just won't render
  }
  return <HRScout data={data} history={history} calibration={calibration} />;
}
