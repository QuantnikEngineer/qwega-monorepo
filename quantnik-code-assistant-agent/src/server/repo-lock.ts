import { execFile } from "node:child_process";
import { access, constants, mkdir, readdir, rm, stat, writeFile } from "node:fs/promises";
import { join, resolve, sep } from "node:path";
import { resolveConfigValue } from "./session-config";

type LockMode = "new" | "existing";
type SyncDirection = "pull" | "push";
type GitAuth = { extraHeader: string };
type FolderMode = "new" | "existing";

export type RepoLockRequest = {
  mode: LockMode;
  folderName: string;
  branchName: string;
  folderMode: FolderMode;
  overwriteExisting?: boolean;
  /** Optional session ID for per-session config lookup */
  sessionId?: string;
};

export type RepoSyncRequest = {
  localPath: string;
  branchName: string;
  direction: SyncDirection;
  /** Optional session ID for per-session config lookup */
  sessionId?: string;
};

const FOLDER_NAME_RE = /^[A-Za-z0-9._-]+$/;

export async function lockLocalRepoWorkspace(input: RepoLockRequest) {
  const remoteUrl = resolveConfigValue(input.sessionId, "repoRemoteUrl", "REPO_LOCK_REMOTE_URL");
  if (!remoteUrl) {
    throw new Error("REPO_LOCK_REMOTE_URL is not configured (set via env or session config)");
  }
  const gitAuth = resolveGitAuth(remoteUrl, input.sessionId);

  const mode = input.mode;
  if (mode !== "new" && mode !== "existing") {
    throw new Error("mode must be either 'new' or 'existing'");
  }

  const folderMode = input.folderMode;
  if (folderMode !== "new" && folderMode !== "existing") {
    throw new Error("folderMode must be either 'new' or 'existing'");
  }

  const folderName = input.folderName.trim();
  if (!FOLDER_NAME_RE.test(folderName)) {
    throw new Error("folderName must contain only letters, numbers, '.', '_' or '-'");
  }

  const branchName = input.branchName.trim();
  if (!branchName) {
    throw new Error("branchName is required");
  }

  const rootDir = await getRepoLockRootDir(input.sessionId);
  const localPath = resolve(join(rootDir, folderName));
  if (!isPathWithinRoot(rootDir, localPath)) {
    throw new Error("folderName resolved outside root directory");
  }

  const folderInfo = await stat(localPath).catch(() => null);

  if (folderMode === "new") {
    if (folderInfo) {
      throw new Error(`local folder already exists: ${localPath}`);
    }
    await mkdir(localPath, { recursive: false });
    await provisionWorkspace(localPath, remoteUrl, mode, branchName, gitAuth);
    return {
      mode,
      folderMode,
      branchName,
      localPath
    };
  }

  if (!folderInfo || !folderInfo.isDirectory()) {
    throw new Error(`local folder does not exist: ${localPath}`);
  }

  if (mode === "new") {
    await prepareExistingFolderForNewBranchPush(localPath, remoteUrl, branchName, gitAuth, input.sessionId);
    return {
      mode,
      folderMode,
      branchName,
      localPath,
      inSync: true
    };
  }

  const syncCheck = await checkExistingFolderSync(localPath, branchName, gitAuth);
  if (!syncCheck.inSync && !input.overwriteExisting) {
    return {
      mode,
      folderMode,
      branchName,
      localPath,
      requiresConfirmation: true,
      warning: syncCheck.warning
    };
  }

  if (!syncCheck.inSync && input.overwriteExisting) {
    await clearDirectoryContents(localPath);
  }

  if (!syncCheck.inSync || !syncCheck.hasGitRepo) {
    await provisionWorkspace(localPath, remoteUrl, mode, branchName, gitAuth);
  }

  if (syncCheck.inSync && mode === "existing") {
    await runGit(["-C", localPath, "checkout", branchName], gitAuth);
    await runGit(["-C", localPath, "pull", "--ff-only", "origin", branchName], gitAuth);
  }

  return {
    mode,
    folderMode,
    branchName,
    localPath,
    inSync: syncCheck.inSync
  };
}

export async function syncLocalRepoWorkspace(input: RepoSyncRequest) {
  const remoteUrl = resolveConfigValue(input.sessionId, "repoRemoteUrl", "REPO_LOCK_REMOTE_URL");
  const gitAuth = resolveGitAuth(remoteUrl, input.sessionId);
  const direction = input.direction;
  if (direction !== "pull" && direction !== "push") {
    throw new Error("direction must be either 'pull' or 'push'");
  }

  const branchName = input.branchName.trim();
  if (!branchName) {
    throw new Error("branchName is required");
  }

  const rootDir = await getRepoLockRootDir(input.sessionId);
  const localPath = resolve(input.localPath.trim());
  if (!isPathWithinRoot(rootDir, localPath)) {
    throw new Error("localPath must be within server root folder");
  }

  const folderInfo = await stat(localPath).catch(() => null);
  if (!folderInfo || !folderInfo.isDirectory()) {
    throw new Error("localPath does not exist");
  }

  await access(join(localPath, ".git"), constants.F_OK);

  await runGit(["-C", localPath, "fetch", "origin", "--prune"], gitAuth);

  if (direction === "pull") {
    await runGit(["-C", localPath, "pull", "--ff-only", "origin", branchName], gitAuth);
  } else {
    await runGit(["-C", localPath, "checkout", branchName], gitAuth);
    await stageAndCommitIfNeeded(localPath, gitAuth, input.sessionId);
    await runGit(["-C", localPath, "push", "origin", branchName], gitAuth);
  }

  return {
    direction,
    branchName,
    localPath
  };
}

async function provisionWorkspace(
  localPath: string,
  remoteUrl: string,
  mode: LockMode,
  branchName: string,
  gitAuth: GitAuth | null
) {
  if (mode === "existing") {
    const branchExists = await remoteBranchExists(remoteUrl, branchName, gitAuth);
    if (!branchExists) {
      throw new Error(`branch '${branchName}' was not found in remote repository`);
    }
    await runGit(["-C", localPath, "clone", "--branch", branchName, "--single-branch", remoteUrl, "."], gitAuth);
    await runGit(["-C", localPath, "pull", "--ff-only", "origin", branchName], gitAuth);
    return;
  }

  const branchExists = await remoteBranchExists(remoteUrl, branchName, gitAuth);
  if (branchExists) {
    throw new Error(`branch '${branchName}' already exists in the remote repository. Use mode 'existing' to work with it.`);
  }

  await runGit(["-C", localPath, "clone", remoteUrl, "."], gitAuth);
  await runGit(["-C", localPath, "checkout", "-b", branchName], gitAuth);
  await runGit(["-C", localPath, "push", "-u", "origin", branchName], gitAuth);
}

async function checkExistingFolderSync(localPath: string, branchName: string, gitAuth: GitAuth | null) {
  const hasGitRepo = await access(join(localPath, ".git"), constants.F_OK)
    .then(() => true)
    .catch(() => false);

  if (!hasGitRepo) {
    return {
      hasGitRepo: false,
      inSync: false,
      warning: "Existing local folder is not a git repository. Confirm overwrite to replace its contents with the remote repository."
    };
  }

  try {
    await runGit(["-C", localPath, "fetch", "origin", branchName], gitAuth);
    const local = await runGit(["-C", localPath, "rev-parse", "HEAD"], gitAuth);
    const remote = await runGit(["-C", localPath, "rev-parse", `origin/${branchName}`], gitAuth);
    const inSync = local.stdout.trim() === remote.stdout.trim();
    return {
      hasGitRepo: true,
      inSync,
      warning: inSync
        ? ""
        : "Local folder is not in sync with remote branch. Confirm overwrite to discard local contents and replace with remote repository content."
    };
  } catch {
    return {
      hasGitRepo: true,
      inSync: false,
      warning: "Could not verify sync state for existing local folder. Confirm overwrite to replace local contents with the remote repository."
    };
  }
}

async function clearDirectoryContents(localPath: string) {
  const items = await readdir(localPath);
  await Promise.all(items.map((item) => rm(join(localPath, item), { recursive: true, force: true })));
}

async function prepareExistingFolderForNewBranchPush(
  localPath: string,
  remoteUrl: string,
  branchName: string,
  gitAuth: GitAuth | null,
  sessionId?: string
) {
  const branchExists = await remoteBranchExists(remoteUrl, branchName, gitAuth);
  if (branchExists) {
    throw new Error(`branch '${branchName}' already exists in the remote repository. Use mode 'existing' to work with it.`);
  }

  const hasGitRepo = await access(join(localPath, ".git"), constants.F_OK)
    .then(() => true)
    .catch(() => false);

  if (!hasGitRepo) {
    await runGit(["-C", localPath, "init"], gitAuth);
  }

  await upsertOriginRemote(localPath, remoteUrl, gitAuth);
  await runGit(["-C", localPath, "checkout", "-B", branchName], gitAuth);
  await stageAndCommitIfNeeded(localPath, gitAuth, sessionId);

  const hasCommit = await runGit(["-C", localPath, "rev-parse", "--verify", "HEAD"], gitAuth)
    .then(() => true)
    .catch(() => false);
  if (!hasCommit) {
    await writeFile(join(localPath, "README.md"), `# ${branchName}\n\nAuto-generated by QUANTNIK.\n`);
    await stageAndCommitIfNeeded(localPath, gitAuth, sessionId);
  }

  await runGit(["-C", localPath, "push", "-u", "origin", branchName], gitAuth);
}

async function upsertOriginRemote(localPath: string, remoteUrl: string, gitAuth: GitAuth | null) {
  const currentOrigin = await runGit(["-C", localPath, "remote", "get-url", "origin"], gitAuth)
    .then((result) => result.stdout.trim())
    .catch(() => "");

  if (!currentOrigin) {
    await runGit(["-C", localPath, "remote", "add", "origin", remoteUrl], gitAuth);
    return;
  }

  if (currentOrigin !== remoteUrl) {
    await runGit(["-C", localPath, "remote", "set-url", "origin", remoteUrl], gitAuth);
  }
}

async function getRepoLockRootDir(sessionId?: string) {
  const configuredRoot = resolveConfigValue(sessionId, "repoRootDir", "REPO_LOCK_ROOT_DIR");
  const rootDir = configuredRoot ? resolve(configuredRoot) : resolve(process.cwd());
  const rootInfo = await stat(rootDir).catch(() => null);
  if (!rootInfo || !rootInfo.isDirectory()) {
    throw new Error(`REPO_LOCK_ROOT_DIR does not exist or is not a directory: ${rootDir}`);
  }
  return rootDir;
}

function isPathWithinRoot(rootDir: string, candidatePath: string) {
  const rootResolved = resolve(rootDir);
  const candidateResolved = resolve(candidatePath);
  const normalizedRoot = rootResolved.toLowerCase();
  const normalizedCandidate = candidateResolved.toLowerCase();
  if (normalizedCandidate === normalizedRoot) {
    return true;
  }
  const rootWithSep = normalizedRoot.endsWith(sep) ? normalizedRoot : `${normalizedRoot}${sep}`;
  return normalizedCandidate.startsWith(rootWithSep);
}

async function stageAndCommitIfNeeded(localPath: string, gitAuth: GitAuth | null, sessionId?: string) {
  await runGit(["-C", localPath, "add", "-A"], gitAuth);
  const status = await runGit(["-C", localPath, "status", "--porcelain"], gitAuth);
  if (!status.stdout.trim()) {
    return;
  }

  const authorName = resolveConfigValue(sessionId, "commitAuthorName", "REPO_LOCK_GIT_COMMIT_AUTHOR_NAME", "QUANTNIK Repo Sync Bot");
  const authorEmail = resolveConfigValue(sessionId, "commitAuthorEmail", "REPO_LOCK_GIT_COMMIT_AUTHOR_EMAIL", "quantnik-repo-sync-bot@local");
  const commitMessage =
    (process.env.REPO_LOCK_GIT_COMMIT_MESSAGE ?? "chore: sync local changes from chat push").trim() ||
    "chore: sync local changes from chat push";

  await runGit([
    "-c",
    `user.name=${authorName}`,
    "-c",
    `user.email=${authorEmail}`,
    "-C",
    localPath,
    "commit",
    "-m",
    commitMessage
  ], gitAuth);
}

async function remoteBranchExists(remoteUrl: string, branchName: string, gitAuth: GitAuth | null) {
  const result = await runGit(["ls-remote", "--heads", remoteUrl, branchName], gitAuth);
  return result.stdout.trim().length > 0;
}

function resolveGitAuth(remoteUrl: string, sessionId?: string): GitAuth | null {
  const token = resolveConfigValue(sessionId, "gitToken", "REPO_LOCK_GIT_TOKEN")
    || resolveConfigValue(sessionId, "gitToken", "REPO_LOCK_GIT_PAT")
    || (process.env.REPO_LOC_PATK_GIT ?? "").trim();
  if (!token) return null;

  if (!remoteUrl.toLowerCase().startsWith("https://")) {
    return null;
  }

  const username = resolveConfigValue(sessionId, "gitUsername", "REPO_LOCK_GIT_USERNAME", "git");
  const encoded = Buffer.from(`${username}:${token}`, "utf8").toString("base64");
  return { extraHeader: `AUTHORIZATION: basic ${encoded}` };
}

async function runGit(args: string[], gitAuth: GitAuth | null = null): Promise<{ stdout: string; stderr: string }> {
  const effectiveArgs = gitAuth?.extraHeader ? ["-c", `http.extraHeader=${gitAuth.extraHeader}`, ...args] : args;
  return await new Promise((resolvePromise, reject) => {
    execFile("git", effectiveArgs, { maxBuffer: 1024 * 1024 * 4 }, (error, stdout, stderr) => {
      if (error) {
        const details = stderr?.trim() || stdout?.trim() || error.message;
        reject(new Error(`git ${redactGitArgs(effectiveArgs).join(" ")} failed: ${details}`));
        return;
      }
      resolvePromise({ stdout, stderr });
    });
  });
}

function redactGitArgs(args: string[]) {
  return args.map((arg) => {
    if (arg.startsWith("http.extraHeader=")) {
      return "http.extraHeader=<redacted>";
    }
    return arg.replace(/https:\/\/[^\s/@]+:[^\s/@]+@/gi, "https://<redacted>@");
  });
}
