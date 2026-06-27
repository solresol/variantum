#!/usr/bin/env node

import os from "node:os";
import fs from "node:fs/promises";
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
    for (const candidate of [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]) {
        if (await executableExists(candidate)) {
            return candidate;
        }
    }
    const cacheRoot = path.join(os.homedir(), "Library", "Caches", "ms-playwright");
    try {
        const entries = await fs.readdir(cacheRoot);
        for (const dir of entries.filter((entry) => entry.startsWith("chromium_headless_shell-")).sort().reverse()) {
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

async function waitForStatus(page, text) {
    await page.waitForFunction(
        (expected) => document.querySelector("[data-form-status]")?.textContent?.trim() === expected,
        text,
        { timeout: 7000 },
    );
}

const baseURL = (process.env.REVIEW_TEST_BASE_URL || "https://parallage.symmachus.org").replace(/\/$/, "");
const username = process.env.REVIEW_TEST_USERNAME;
const password = process.env.REVIEW_TEST_PASSWORD;
if (!username || !password) {
    throw new Error("Set REVIEW_TEST_USERNAME and REVIEW_TEST_PASSWORD for the temporary reviewer account.");
}

const playwright = await importPlaywright();
const chromium = playwright.chromium || playwright.default?.chromium;
if (!chromium) {
    throw new Error("Playwright was loaded, but no chromium browser export was found.");
}

const browser = await chromium.launch({
    headless: true,
    ...((await findChromiumExecutable()) ? { executablePath: await findChromiumExecutable() } : {}),
});

try {
    const page = await browser.newPage({
        viewport: { width: 1280, height: 720 },
        httpCredentials: { username, password },
    });

    const startURL = `${baseURL}/review/stephanos-review-v1/passages/2330.html`;
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(startURL, { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".rating-grid-11 input[value='6']");
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
    await page.waitForSelector(".rating-grid-11 input[value='6']");
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
    await page.waitForTimeout(500);
    await page.locator('.rating-grid-11 input[value="6"]').click({ force: true });
    await waitForStatus(page, "Saved.");

    await page.getByRole("link", { name: "Next" }).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("link", { name: "Previous" }).click();
    await page.waitForLoadState("domcontentloaded");
    await page.waitForFunction(() => document.querySelector('.rating-grid-11 input[value="6"]')?.checked === true, null, {
        timeout: 7000,
    });

    await page.locator('.rating-grid-11 input[value="9"]').click({ force: true });
    await waitForStatus(page, "Saved.");
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => document.querySelector('.rating-grid-11 input[value="9"]')?.checked === true, null, {
        timeout: 7000,
    });

    const checkedValue = await page.locator(".rating-grid-11 input:checked").getAttribute("value");
    console.log(JSON.stringify({ ok: true, checkedValue, url: page.url() }, null, 2));
} finally {
    await browser.close();
}
