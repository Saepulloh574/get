const { chromium } = require('playwright');
const { Mutex } = require('async-mutex');
const HEADLESS_CONFIG = require('./headless.js');
const { performLogin } = require('./login.js');

let browserServer = null;
let browser = null;
let sharedContext = null; // Kunci: Context harus dishare
const initLock = new Mutex();
const LOGIN_URL = "https://stexsms.com/mauth/login";

async function initSharedBrowser(email, password) {
    const release = await initLock.acquire();
    try {
        if (browserServer && browser && browser.isConnected()) return browserServer.wsEndpoint();

        console.log("[SHARED] Meluncurkan Chromium Server Utama...");
        browserServer = await chromium.launchServer({
            headless: HEADLESS_CONFIG.headless,
            handleSIGINT: false,
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });

        const wsEndpoint = browserServer.wsEndpoint();
        browser = await chromium.connect(wsEndpoint);
        
        // Buat context sekali saja di sini
        sharedContext = await browser.newContext({
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
        });

        const loginPage = await sharedContext.newPage();
        try {
            await performLogin(loginPage, email, password, LOGIN_URL);
            await loginPage.waitForLoadState('networkidle');
            console.log("[SHARED] ✅ Login Berhasil di Tab 1.");
        } finally {
            // JANGAN tutup context, cuma tutup page login kalau sudah selesai (optional)
            // Kalau mau tetap kelihatan loginnya, jangan diclose page-nya.
        }
        return wsEndpoint;
    } finally {
        release();
    }
}

async function getNewPage() {
    if (!sharedContext) throw new Error("Context belum ada!");
    return await sharedContext.newPage();
}

module.exports = { initSharedBrowser, getNewPage };
