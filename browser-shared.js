const { chromium } = require('playwright');
const { Mutex } = require('async-mutex');
const HEADLESS_CONFIG = require('./headless.js');
const { performLogin } = require('./login.js');
const { state } = require('./helpers/state');

let browserServer = null;
let browser = null;
let context = null;
const initLock = new Mutex();
const LOGIN_URL = "https://stexsms.com/mauth/login";

async function initSharedBrowser(email, password) {
    const release = await initLock.acquire();
    try {
        if (browserServer && browser && browser.isConnected()) return state.wsEndpoint;

        console.log("[SHARED-BROWSER] Meluncurkan Chromium Server...");
        
        browserServer = await chromium.launchServer({
            headless: HEADLESS_CONFIG.headless,
            handleSIGINT: false, 
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });

        state.wsEndpoint = browserServer.wsEndpoint();
        console.log(`[SHARED-BROWSER] WS Endpoint: ${state.wsEndpoint}`);

        browser = await chromium.connect(state.wsEndpoint);
        state.browser = browser; 

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
        return state.wsEndpoint;
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
