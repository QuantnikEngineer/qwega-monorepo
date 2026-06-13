import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SEED_DIR = path.resolve(__dirname, '..', 'seed-skills');
const TARGET_DIR = path.join(os.homedir(), '.claude', 'skills');

function copyDirRecursive(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDirRecursive(s, d);
    else if (entry.isFile()) fs.copyFileSync(s, d);
  }
}

function filesIdentical(a, b) {
  if (!fs.existsSync(a) || !fs.existsSync(b)) return false;
  const sa = fs.statSync(a), sb = fs.statSync(b);
  if (sa.size !== sb.size) return false;
  // Cheap content check on the SKILL.md (the only file that matters semantically).
  try {
    return fs.readFileSync(a).equals(fs.readFileSync(b));
  } catch { return false; }
}

// Seed skills from the quantnik repo's `seed-skills/` directory into the user's
// `~/.claude/skills/` so the Claude Agent SDK can load them. Runs at startup.
//
// Behaviour:
// - If a target skill doesn't exist, copy it.
// - If a target skill exists but its SKILL.md content differs from the seed,
//   overwrite the whole directory. (Lets new committed versions flow on every
//   cloud redeploy.)
// - Set SKIP_SKILL_SEED=1 in .env to opt out — useful on a developer box
//   where the user actively edits `~/.claude/skills/<x>/SKILL.md` and doesn't
//   want the repo's version to win on every restart.
export function seedSkills() {
  if (process.env.SKIP_SKILL_SEED === '1') {
    console.log('[seed-skills] SKIP_SKILL_SEED=1 — skipping');
    return;
  }
  if (!fs.existsSync(SEED_DIR)) {
    console.log(`[seed-skills] no seed dir at ${SEED_DIR}, skipping`);
    return;
  }
  fs.mkdirSync(TARGET_DIR, { recursive: true });

  let copied = 0, updated = 0, skipped = 0;
  for (const entry of fs.readdirSync(SEED_DIR, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const skillName = entry.name;
    const srcSkill = path.join(SEED_DIR, skillName);
    const srcMd = path.join(srcSkill, 'SKILL.md');
    if (!fs.existsSync(srcMd)) continue;

    const destSkill = path.join(TARGET_DIR, skillName);
    const destMd = path.join(destSkill, 'SKILL.md');

    if (!fs.existsSync(destSkill)) {
      copyDirRecursive(srcSkill, destSkill);
      copied++;
    } else if (!filesIdentical(srcMd, destMd)) {
      // Overwrite — newer committed version wins.
      fs.rmSync(destSkill, { recursive: true, force: true });
      copyDirRecursive(srcSkill, destSkill);
      updated++;
    } else {
      skipped++;
    }
  }
  console.log(`[seed-skills] ${copied} new, ${updated} updated, ${skipped} unchanged → ${TARGET_DIR}`);
}
