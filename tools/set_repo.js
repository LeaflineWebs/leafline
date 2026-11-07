// Tells the installer build where updates are published (the GitHub repository from github.txt, or GITHUB_REPOSITORY in the cloud build).
const fs = require("fs"), path = require("path");
const root = path.join(__dirname, "..");
const pkgPath = path.join(root, "package.json"), pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
let repo = (process.env.GITHUB_REPOSITORY || "").trim();
if (!repo) { try { repo = fs.readFileSync(path.join(root, "github.txt"), "utf8").split(/\r?\n/).map((l) => l.trim()).find((l) => l && !l.startsWith("#")) || ""; } catch (_) {} }
const m = /^([A-Za-z0-9-]+)\/([A-Za-z0-9._-]+)$/.exec(repo);
if (!m || /^YOUR-/i.test(m[1])) {
  delete pkg.build.publish;
  console.log("No GitHub repository set (run SETUP_GITHUB.bat). Building without automatic updates.");
} else {
  pkg.build.publish = [{ provider: "github", owner: m[1], repo: m[2], releaseType: "release" }];
  console.log("Updates will be published to https://github.com/" + m[1] + "/" + m[2]);
}
fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n");
