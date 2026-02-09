const { chromium } = require('playwright');
const { Mutex } = require('async-mutex');
const HEADLESS_CONFIG = require('./headless.js');
const { performLogin } = require('./login.js');

let browserServer = null; // Ubah ini
let browser = null;
let context = null;
let wsEndpoint = null;
const initLock = new Mutex();
const LOGIN_URL = "https://stexsms.com/mauth/login";

async function initSharedBrowser(email, password) {
    const release = await initLock.acquire();
    try {
        if (browserServer && browser && browser.isConnected()) return wsEndpoint;

        console.log("[SHARED-BROWSER] Meluncurkan Chromium Server...");
        
        // KUNCI: Pakai launchServer agar wsEndpoint tersedia
        browserServer = await chromium.launchServer({
    headless: HEADLESS_CONFIG.headless,
    handleSIGINT: false, // Tambahkan ini agar server gak mati saat main.js restart
    args: ['--no-sandbox', '--disable-setuid-sandbox']
});

        wsEndpoint = browserServer.wsEndpoint();
        console.log(`[SHARED-BROWSER] WS Endpoint: ${wsEndpoint}`);

        // Konek ke server sendiri untuk membuat context
        browser = await chromium.connect(wsEndpoint);
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
    } catch (error) {
        console.error("[SHARED-BROWSER] Gagal inisialisasi:", error);
        throw error;
    } finally {
        release();
    }
}

async function getNewPage() {
    if (!context) throw new Error("Context belum dibuat!");
    return await context.newPage();
}

async function restartBrowser(email, password) {
    if (browser) await browser.close().catch(() => {});
    if (browserServer) await browserServer.close().catch(() => {});
    browser = null;
    browserServer = null;
    context = null;
    return await initSharedBrowser(email, password);
}

module.exports = { initSharedBrowser, getNewPage, restartBrowser };
