// browser-shared.js
const { chromium } = require('playwright');
const { Mutex } = require('async-mutex');
const HEADLESS_CONFIG = require('./headless.js'); // Pastikan file ini ada
const { performLogin } = require('./login.js');   // Pastikan file ini ada

// Variabel Global Shared
let browser = null;
let context = null;
const initLock = new Mutex(); // Lock hanya untuk proses init/restart

// Config Login (Sesuaikan jika perlu, atau ambil dari parameter)
const LOGIN_URL = "https://stexsms.com/mauth/login";

/**
 * 1. Inisialisasi Browser & Login (Hanya dipanggil sekali oleh main.js)
 */
async function initSharedBrowser(email, password) {
    if (browser && context) return; // Jika sudah jalan, skip

    const release = await initLock.acquire();
    try {
        if (browser) return; // Double check

        console.log("[SHARED-BROWSER] Meluncurkan Chromium...");
        browser = await chromium.launch({
            headless: HEADLESS_CONFIG.headless,
            args: [
                '--no-sandbox', 
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage', // Penting untuk VPS memory kecil
                '--disable-gpu'
            ]
        });

        console.log("[SHARED-BROWSER] Membuat Context (Session)...");
        // Context ini menyimpan cookies/session login
        context = await browser.newContext({
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
        });

        // --- PROSES LOGIN ---
        console.log(`[SHARED-BROWSER] Login sebagai ${email}...`);
        const loginPage = await context.newPage();
        
        try {
            // Menggunakan fungsi login dari login.js yang Anda punya
            await performLogin(loginPage, email, password, LOGIN_URL);
            
            // Verifikasi Login (Opsional: cek apakah redirect berhasil)
            await loginPage.waitForTimeout(3000); 
            console.log("[SHARED-BROWSER] ✅ Login Sukses! Session tersimpan di Context.");
            
        } catch (e) {
            console.error("[SHARED-BROWSER] ❌ Login Gagal:", e);
            throw e; // Lempar error agar main.js tahu
        } finally {
            await loginPage.close(); // Tutup tab login, session sudah aman di context
        }

    } finally {
        release();
    }
}

/**
 * 2. Minta Tab Baru (Page)
 * Digunakan oleh main.js, range.js, message.js
 */
async function getNewPage() {
    if (!context) {
        throw new Error("Browser belum init! Jalankan main.js dulu.");
    }
    // Halaman baru ini otomatis sudah LOGIN karena satu context
    const page = await context.newPage();
    return page;
}

/**
 * 3. Restart Browser (Untuk Cron Job atau Error Handling)
 */
async function restartBrowser(email, password) {
    const release = await initLock.acquire();
    try {
        if (browser) {
            console.log("[SHARED-BROWSER] Menutup browser lama...");
            await browser.close();
        }
        browser = null;
        context = null;
    } finally {
        release();
    }
    // Init ulang
    await initSharedBrowser(email, password);
}

module.exports = { initSharedBrowser, getNewPage, restartBrowser };
