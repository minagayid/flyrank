import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
import type { FlowRun, RunLogEntry } from "./types";

const storageDirectory = process.env.DATA_DIR || path.join(process.cwd(), "data");
const storagePath = path.join(storageDirectory, "runs.json");
let writeQueue: Promise<void> = Promise.resolve();

async function readRuns(): Promise<FlowRun[]> {
  try {
    return JSON.parse(await readFile(storagePath, "utf8")) as FlowRun[];
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw error;
  }
}

function serialized<T>(operation: () => Promise<T>): Promise<T> {
  const result = writeQueue.then(operation);
  writeQueue = result.then(() => undefined, () => undefined);
  return result;
}

async function persist(runs: FlowRun[]): Promise<void> {
  await mkdir(storageDirectory, { recursive: true });
  const temporaryPath = `${storagePath}.tmp`;
  await writeFile(temporaryPath, JSON.stringify(runs, null, 2), "utf8");
  await rename(temporaryPath, storagePath);
}

export async function listRuns(): Promise<FlowRun[]> {
  await writeQueue;
  return (await readRuns()).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function getRun(id: string): Promise<FlowRun | undefined> {
  await writeQueue;
  return (await readRuns()).find((run) => run.id === id);
}

export function createRun(
  input: Omit<FlowRun, "id" | "createdAt" | "updatedAt" | "logs">,
): Promise<FlowRun> {
  return serialized(async () => {
    const now = new Date().toISOString();
    const run: FlowRun = { ...input, id: randomUUID(), createdAt: now, updatedAt: now, logs: [] };
    const runs = await readRuns();
    runs.push(run);
    await persist(runs);
    return run;
  });
}

export function updateRun(id: string, update: Partial<FlowRun>): Promise<FlowRun | undefined> {
  return serialized(async () => {
    const runs = await readRuns();
    const index = runs.findIndex((run) => run.id === id);
    if (index < 0) return undefined;
    runs[index] = { ...runs[index], ...update, updatedAt: new Date().toISOString() };
    await persist(runs);
    return runs[index];
  });
}

export function appendLog(id: string, entry: RunLogEntry): Promise<FlowRun | undefined> {
  return serialized(async () => {
    const runs = await readRuns();
    const index = runs.findIndex((run) => run.id === id);
    if (index < 0) return undefined;
    runs[index].logs.push(entry);
    runs[index].updatedAt = new Date().toISOString();
    await persist(runs);
    return runs[index];
  });
}
