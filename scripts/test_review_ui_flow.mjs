#!/usr/bin/env node

import fs from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

async function importPlaywright() {
    try {
        return await import(require.resolve("playwright"));
    } catch (error) {
        throw new Error(
            "Playwright is required for this test. Install it for this repo or run with NODE_PATH pointing at a node_modules directory that contains playwright.",
            { cause: error },
        );
    }
}

function contentType(filePath) {
    if (filePath.endsWith(".html")) return "text/html; charset=utf-8";
    if (filePath.endsWith(".css")) return "text/css; charset=utf-8";
    if (filePath.endsWith(".js")) return "application/javascript; charset=utf-8";
    return "application/octet-stream";
}

function serveStatic(root) {
    const server = http.createServer(async (request, response) => {
        try {
            const url = new URL(request.url || "/", "http://127.0.0.1");
            let filePath = path.join(root, decodeURIComponent(url.pathname));
            if (url.pathname.endsWith("/")) {
                filePath = path.join(filePath, "index.html");
            }
            const relative = path.relative(root, filePath);
            if (relative.startsWith("..") || path.isAbsolute(relative)) {
                response.writeHead(403).end("Forbidden");
                return;
            }
            const body = await fs.readFile(filePath);
            response.writeHead(200, { "Content-Type": contentType(filePath) });
            response.end(body);
        } catch {
            response.writeHead(404).end("Not found");
        }
    });
    return new Promise((resolve) => {
        server.listen(0, "127.0.0.1", () => resolve(server));
    });
}

function waitFor(predicate, description, timeoutMs = 3000) {
    const started = Date.now();
    return new Promise((resolve, reject) => {
        const tick = () => {
            if (predicate()) {
                resolve();
                return;
            }
            if (Date.now() - started > timeoutMs) {
                reject(new Error(`Timed out waiting for ${description}`));
                return;
            }
            setTimeout(tick, 25);
        };
        tick();
    });
}

function latestRatings(transactions, packSlug, passageID) {
    const ratings = {};
    for (const transaction of transactions) {
        if (transaction.packSlug === packSlug && transaction.passageID === passageID) {
            ratings[transaction.variantID] = {
                rating: Number(transaction.rating),
                most_trusted: false,
                least_trusted: false,
                notes: "",
                updated_at: transaction.savedAt,
            };
        }
    }
    return ratings;
}

function maxVisibleMs(transaction) {
    const rows = Object.values(transaction.exposure.variants || {});
    return rows.reduce((max, row) => Math.max(max, Number(row.visible_ms || 0)), 0);
}

async function executableExists(filePath) {
    try {
        await fs.access(filePath);
        return true;
    } catch {
        return false;
    }
}

async function findChromiumExecutable() {
    if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE) {
        return process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
    }
    const macApps = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ];
    for (const candidate of macApps) {
        if (await executableExists(candidate)) {
            return candidate;
        }
    }
    const cacheRoot = path.join(os.homedir(), "Library", "Caches", "ms-playwright");
    try {
        const entries = await fs.readdir(cacheRoot);
        const shellDirs = entries
            .filter((entry) => entry.startsWith("chromium_headless_shell-"))
            .sort()
            .reverse();
        for (const dir of shellDirs) {
            const candidate = path.join(cacheRoot, dir, "chrome-headless-shell-mac-arm64", "chrome-headless-shell");
            if (await executableExists(candidate)) {
                return candidate;
            }
        }
    } catch {
        return "";
    }
    return "";
}

const siteRoot = path.resolve("site");
const playwright = await importPlaywright();
const chromium = playwright.chromium || playwright.default?.chromium;
if (!chromium) {
    throw new Error("Playwright was loaded, but no chromium browser export was found.");
}
const server = await serveStatic(siteRoot);
const { port } = server.address();
const baseURL = `http://127.0.0.1:${port}`;
const transactions = [];
let browser;

try {
    const executablePath = await findChromiumExecutable();
    browser = await chromium.launch({
        headless: true,
        ...(executablePath ? { executablePath } : {}),
    });
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });

    await page.route("**/cgi-bin/review-state.cgi?**", async (route) => {
        const url = new URL(route.request().url());
        const packSlug = url.searchParams.get("pack_slug") || "";
        const passageID = Number(url.searchParams.get("passage_id") || "0");
        await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
                reviewer: "test-reviewer",
                pack_slug: packSlug,
                passage_id: passageID,
                ratings: latestRatings(transactions, packSlug, passageID),
            }),
        });
    });

    await page.route("**/cgi-bin/review-save.cgi", async (route) => {
        const params = new URLSearchParams(route.request().postData() || "");
        const packSlug = params.get("pack_slug") || "";
        const passageID = Number(params.get("passage_id") || "0");
        const exposure = JSON.parse(params.get("exposure_json") || "{}");
        for (const variantID of params.getAll("variant_id")) {
            transactions.push({
                packSlug,
                passageID,
                variantID,
                rating: params.get(`rating_${variantID}`),
                exposure,
                savedAt: new Date().toISOString(),
            });
        }
        await route.fulfill({ status: 200, contentType: "text/plain", body: "saved" });
    });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${baseURL}/review/stephanos-review-v1/passages/2330.html`, { waitUntil: "domcontentloaded" });
    const mobileLayout = await page.evaluate(() => {
        const ratingBar = document.querySelector(".rating-grid-11");
        const rect = ratingBar.getBoundingClientRect();
        return {
            viewportWidth: document.documentElement.clientWidth,
            documentScrollWidth: document.documentElement.scrollWidth,
            bodyScrollWidth: document.body.scrollWidth,
            ratingLeft: Math.round(rect.left),
            ratingRight: Math.round(rect.right),
            ratingWidth: Math.round(rect.width),
        };
    });
    if (
        mobileLayout.documentScrollWidth > mobileLayout.viewportWidth + 1 ||
        mobileLayout.bodyScrollWidth > mobileLayout.viewportWidth + 1
    ) {
        throw new Error(`Mobile layout has horizontal overflow: ${JSON.stringify(mobileLayout)}`);
    }
    if (mobileLayout.ratingLeft < 0 || mobileLayout.ratingRight > mobileLayout.viewportWidth + 1) {
        throw new Error(`Mobile rating bar does not fit viewport: ${JSON.stringify(mobileLayout)}`);
    }
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.reload({ waitUntil: "domcontentloaded" });
    if ((await page.getByRole("button", { name: "Save Rating" }).count()) !== 0) {
        throw new Error("Passage page should not render a Save Rating button; number clicks autosave.");
    }
    if ((await page.getByRole("link", { name: "Back to Set 1" }).count()) !== 1) {
        throw new Error("Expected Back to Set 1 link in the top passage navigation.");
    }
    const scrollPrompt = page.getByText("Scroll down to see alternate translations.", { exact: true });
    if (!(await scrollPrompt.isVisible())) {
        throw new Error("Expected scroll prompt to be visible before helper translations are revealed.");
    }
    await page.mouse.wheel(0, 420);
    await page.waitForFunction(() => document.body.classList.contains("helpers-visible"));
    if (await scrollPrompt.isVisible()) {
        throw new Error("Expected scroll prompt to be hidden after helper translations are revealed.");
    }
    if (
        !(await page
            .getByText("The following Parallage translations might help you judge how different a human translation is likely to be.", {
                exact: true,
            })
            .isVisible())
    ) {
        throw new Error("Expected helper heading to be visible after scrolling.");
    }
    await page.waitForTimeout(700);
    await page.locator('.rating-grid-11 input[value="6"]').click({ force: true });
    await waitFor(() => transactions.length === 1, "first autosave transaction");
    const firstExposureMs = maxVisibleMs(transactions[0]);
    if (firstExposureMs <= 0) {
        throw new Error(`Expected first transaction to include visible helper timing, got ${firstExposureMs}`);
    }

    await page.waitForTimeout(150);
    await page.locator('.rating-grid-11 input[value="9"]').click({ force: true });
    await waitFor(() => transactions.length === 2, "second autosave transaction");
    const secondExposureMs = maxVisibleMs(transactions[1]);
    if (!(secondExposureMs > 0 && secondExposureMs < firstExposureMs)) {
        throw new Error(
            `Expected second transaction timing to reset after first click; first=${firstExposureMs}, second=${secondExposureMs}`,
        );
    }

    await page.getByRole("link", { name: "Next" }).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("link", { name: "Previous" }).click();
    await page.waitForLoadState("domcontentloaded");
    await page.waitForFunction(() => document.querySelector('.rating-grid-11 input[value="9"]')?.checked === true);

    const checkedValue = await page.locator(".rating-grid-11 input:checked").getAttribute("value");
    if (checkedValue !== "9") {
        throw new Error(`Expected latest rating 9 to be highlighted after Next/Previous, got ${checkedValue}`);
    }

    console.log(
        JSON.stringify(
            {
                ok: true,
                transactions: transactions.length,
                firstExposureMs,
                secondExposureMs,
                restoredRating: checkedValue,
            },
            null,
            2,
        ),
    );
} finally {
    if (browser) {
        await browser.close();
    }
    await new Promise((resolve) => server.close(resolve));
}
