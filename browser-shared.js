const puppeteer = require('puppeteer-core'); // Gunakan puppeteer-core untuk Termux
const { Mutex } = require('async-mutex');
const HEADLESS_CONFIG = require('./headless.js');
const { performLogin } = require('./login.js');

let browser = null;
let sharedBrowserWSEndpoint = null;
const initLock = new Mutex();
const LOGIN_URL = "https://stexsms.com/mauth/login";

/**
 * Inisialisasi Browser Puppeteer dan melakukan login
 */
async function initSharedBrowser(email, password) {
    const release = await initLock.acquire();
    try {
        // Jika browser sudah ada dan masih terkoneksi, kembalikan endpoint yang ada
        if (browser && browser.isConnected()) {
            return sharedBrowserWSEndpoint;
        }

        console.log("[SHARED] Meluncurkan Puppeteer (Chromium) Utama...");
        
        // Konfigurasi launch untuk Puppeteer
        browser = await puppeteer.launch({
            headless: HEADLESS_CONFIG.headless,
            executablePath: '/usr/bin/chromium-browser', // Path standar Chromium di Termux
            handleSIGINT: false,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--window-size=1280,720'
            ]
        });

        sharedBrowserWSEndpoint = browser.wsEndpoint();

        // Di Puppeteer, "Context" biasanya default. 
        // Kita langsung buat page pertama untuk login.
        const pages = await browser.pages();
        const loginPage = pages.length > 0 ? pages[0] : await browser.newPage();

        try {
            // Set User Agent agar tidak terdeteksi bot
            await loginPage.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36');
            
            await performLogin(loginPage, email, password, LOGIN_URL);
            
            // Tunggu sampai navigasi tenang (Pengganti waitForLoadState)
            await loginPage.waitForNavigation({ waitUntil: 'networkidle2' }).catch(() => null);
            
            console.log("[SHARED] ✅ Login Berhasil via Puppeteer.");
        } catch (loginError) {
            console.error("[SHARED] ❌ Gagal Login:", loginError.message);
        }

        return sharedBrowserWSEndpoint;
    } finally {
        release();
    }
}

/**
 * Membuat tab baru di dalam browser yang sudah login
 */
async function getNewPage() {
    if (!browser) throw new Error("Browser belum diinisialisasi!");
    
    const page = await browser.newPage();
    // Set viewport standar
    await page.setViewport({ width: 1280, height: 720 });
    return page;
}

/**
 * Fungsi tambahan untuk restart browser jika diperlukan (opsional)
 */
async function restartBrowser(email, password) {
    if (browser) {
        await browser.close();
        browser = null;
    }
    return await initSharedBrowser(email, password);
}

module.exports = { 
    initSharedBrowser, 
    getNewPage, 
    restartBrowser 
};
