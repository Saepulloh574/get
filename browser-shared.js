const { chromium } = require('playwright');
const { Mutex } = require('async-mutex');
const HEADLESS_CONFIG = require('./headless.js');
const { performLogin } = require('./login.js');

let browser = null;
let context = null;
let wsEndpoint = null; // Tambahkan ini untuk sharing alamat browser
const initLock = new Mutex();
const LOGIN_URL = "https://stexsms.com/mauth/login";

async function initSharedBrowser(email, password) {
    const release = await initLock.acquire();
    try {
        if (browser && browser.isConnected()) return;

        console.log("[SHARED] Launching Chromium...");
        browser = await chromium.launch({
            headless: HEADLESS_CONFIG.headless,
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        });

        // Simpan alamat websocket agar script lain bisa connect
        wsEndpoint = browser.wsEndpoint(); 

        context = await browser.newContext({
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
        });

        const loginPage = await context.newPage();
        try {
            await performLogin(loginPage, email, password, LOGIN_URL);
            await loginPage.waitForLoadState('networkidle');
            console.log("[SHARED] ✅ Login Berhasil.");
        } finally {
            await loginPage.close();
        }
    } finally {
        release();
    }
}

async function getNewPage() {
    // Jika dipanggil dari script lain (child process), kita connect ulang via WS
    if (!context || !browser.isConnected()) {
        if (!wsEndpoint) throw new Error("Browser belum Ready!");
        const remoteBrowser = await chromium.connectOverCDP(wsEndpoint);
        const remoteContext = remoteBrowser.contexts()[0];
        return await remoteContext.newPage();
    }
    return await context.newPage();
}

module.exports = { initSharedBrowser, getNewPage };
