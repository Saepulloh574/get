// browser-shared.js
const { chromium } = require('playwright');
const { Mutex } = require('async-mutex');
const HEADLESS_CONFIG = require('./headless.js');
const { performLogin } = require('./login.js');

let browser = null;
let context = null;
let wsEndpoint = null; // KUNCI UTAMA
const initLock = new Mutex();
const LOGIN_URL = "https://stexsms.com/mauth/login";

async function initSharedBrowser(email, password) {
    const release = await initLock.acquire();
    try {
        if (browser && browser.isConnected()) return wsEndpoint;

        console.log("[SHARED-BROWSER] Meluncurkan Chromium...");
        browser = await chromium.launch({
            headless: HEADLESS_CONFIG.headless,
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        });

        wsEndpoint = browser.wsEndpoint(); 

        context = await browser.newContext({
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
        });

        const loginPage = await context.newPage();
        try {
            await performLogin(loginPage, email, password, LOGIN_URL);
            await loginPage.waitForLoadState('networkidle');
            console.log("[SHARED-BROWSER] ✅ Login Berhasil.");
        } finally {
            await loginPage.close();
        }
        return wsEndpoint;
    } finally {
        release();
    }
}

async function getNewPage() {
    if (!context || !browser.isConnected()) {
        throw new Error("Browser belum init atau terputus!");
    }
    return await context.newPage();
}

async function restartBrowser(email, password) {
    if (browser) await browser.close().catch(() => {});
    browser = null;
    context = null;
    return await initSharedBrowser(email, password);
}

module.exports = { initSharedBrowser, getNewPage, restartBrowser };
