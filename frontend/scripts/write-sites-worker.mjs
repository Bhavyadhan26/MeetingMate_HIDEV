import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { extname, join, relative, sep } from "node:path";

const serverDir = join(process.cwd(), "dist", "server");
await mkdir(serverDir, { recursive: true });

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".map": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".webp": "image/webp"
};

async function listFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "server") continue;
      files.push(...await listFiles(fullPath));
    } else {
      files.push(fullPath);
    }
  }
  return files;
}

const distDir = join(process.cwd(), "dist");
const assets = {};
for (const filePath of await listFiles(distDir)) {
  const key = `/${relative(distDir, filePath).split(sep).join("/")}`;
  const body = await readFile(filePath);
  assets[key] = {
    body: body.toString("base64"),
    contentType: contentTypes[extname(filePath)] || "application/octet-stream"
  };
}

await writeFile(
  join(serverDir, "index.js"),
  `const assets = ${JSON.stringify(assets)};

function decodeBase64(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = assets[url.pathname] ? url.pathname : "/index.html";
    const asset = assets[path];
    if (!asset) {
      return new Response("Not found", { status: 404 });
    }
    return new Response(decodeBase64(asset.body), {
      headers: {
        "content-type": asset.contentType,
        "cache-control": path.startsWith("/assets/") ? "public, max-age=31536000, immutable" : "no-store"
      }
    });
  }
};
`,
  "utf8"
);
