// electron-builder "afterPack" step. Apple Silicon Macs refuse to run an app whose code has no valid signature, and
// with no paid Apple certificate electron-builder skips signing altogether. This gives the finished app a free
// "ad-hoc" signature (the same kind Xcode uses for local builds) before it is packed into the .dmg and .zip.
// The first launch still needs right-click > Open, because the app isn't notarized by Apple.
const { execFileSync } = require("child_process");
const path = require("path");
exports.default = async function (ctx) {
  if (ctx.electronPlatformName !== "darwin") return;
  const app = path.join(ctx.appOutDir, ctx.packager.appInfo.productFilename + ".app");
  console.log("  • ad-hoc signing " + app);
  execFileSync("codesign", ["--force", "--deep", "--sign", "-", app], { stdio: "inherit" });
  execFileSync("codesign", ["--verify", "--deep", "--strict", app], { stdio: "inherit" });
};
