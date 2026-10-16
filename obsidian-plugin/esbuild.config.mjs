import esbuild from "esbuild";
import builtins from "builtin-modules";

const mode = process.argv[2];           // production | test | (empty = dev, with watch)
const common = {
  bundle: true,
  format: "cjs",
  target: "es2020",
  logLevel: "info",
  sourcemap: mode === "production" ? false : "inline",
  treeShaking: true,
};

if (mode === "test") {
  await esbuild.build({ ...common, platform: "node", entryPoints: ["test/engine.test.ts"], outfile: "dist-test/engine.test.cjs" });
} else {
  const ctx = await esbuild.context({
    ...common,
    entryPoints: ["src/main.ts"],
    external: ["obsidian", "electron", "@codemirror/*", "@lezer/*", ...builtins],
    outfile: "main.js",
  });
  if (mode === "production") { await ctx.rebuild(); process.exit(0); }
  await ctx.watch();
}
