import { readdir, stat } from "node:fs/promises";
import { isAbsolute, join, resolve } from "node:path";

export type RepoInfo = { repoRoot: string; workdir: string };

async function ensureDirectory(path: string): Promise<string> {
  const info = await stat(path);
  if (!info.isDirectory()) {
    throw new Error(`not a directory: ${path}`);
  }
  return path;
}

export async function getLocalRepoInfo(repoInput?: string): Promise<RepoInfo> {
  const normalized = typeof repoInput === "string" ? repoInput.trim() : "";
  if (normalized) {
    const directPath = isAbsolute(normalized) ? normalized : resolve(normalized);
    try {
      const repoDir = await ensureDirectory(directPath);
      return { repoRoot: repoDir, workdir: repoDir };
    } catch {
      try {
        const underRepos = join("./repos", normalized);
        const repoDir = await ensureDirectory(underRepos);
        return { repoRoot: repoDir, workdir: repoDir };
      } catch {
        console.warn(`[repo] Provided repo path "${normalized}" not found, falling back to default scan`);
      }
    }
  }

  const base = "./repos";
  const entries = await readdir(base, { withFileTypes: true });
  const first = entries.find((e) => e.isDirectory());
  if (!first) {
    throw new Error("no repository found under ./repos");
  }
  const repoDir = join(base, first.name);
  await ensureDirectory(repoDir);
  return { repoRoot: repoDir, workdir: repoDir };
}

