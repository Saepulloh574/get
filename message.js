const axios = require('axios');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

// Mengambil state global agar berbagi instance browser dengan main process
const { state } = require('./helpers/state'); 

// ==================== KONFIGURASI ====================
const BOT_TOKEN = "7562117237:AAFQnb5aCmeSHHi_qAJz3vkoX4HbNGohe38";
const CHAT_ID = "-1003492226491"; 
const ADMIN_ID = "7184123643";
const TELEGRAM_BOT_LINK = "https://t.me/myzuraisgoodbot";
const TELEGRAM_ADMIN_LINK = "https://t.me/Imr1d";

const DASHBOARD_URL = "https://stexsms.com/mdashboard/getnum";
const SMC_JSON_FILE = path.join(__dirname, "smc.json");
const WAIT_JSON_FILE = path.join(__dirname, "wait.json");
const CACHE_FILE = path.join(__dirname, 'otp_cache.json');

// Database Emoji
let COUNTRY_EMOJI = {};
try {
    COUNTRY_EMOJI = require('./country.json');
} catch (e) {
    console.error("⚠️ [MESSAGE] country.json missing.");
}

let monitorPage = null;

// ==================== UTILS ====================

const escapeHtml = (text) => (text ? text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") : "");
const getCountryEmoji = (c) => (COUNTRY_EMOJI[c?.trim().toUpperCase()] || "🏴‍☠️");

// --- FUNGSI AMBIL PAGE (SUPPORT SHARED STATE & WS) ---
async function getSharedPage() {
    try {
        if (state && state.browser) {
            const contexts = state.browser.contexts();
            const context = contexts.length > 0 ? contexts[0] : await state.browser.newContext();
            return await context.newPage();
        } 
        else if (process.env.WS_ENDPOINT) {
            const browser = await chromium.connect(process.env.WS_ENDPOINT);
            const context = browser.contexts()[0] || await browser.newContext();
            return await context.newPage();
        } 
        else {
            console.error("❌ [MESSAGE] Browser instance tidak ditemukan.");
            return null;
        }
    } catch (e) {
        console.error("❌ [MESSAGE] Gagal mendapatkan Page:", e.message);
        return null;
    }
}

function getCache() {
    if (fs.existsSync(CACHE_FILE)) {
        try { return JSON.parse(fs.readFileSync(CACHE_FILE)); } catch (e) { return {}; }
    }
    return {};
}

function saveToCache(cache) {
    const keys = Object.keys(cache);
    if (keys.length > 500) {
        const newCache = {};
        keys.slice(-500).forEach(k => newCache[k] = cache[k]);
        fs.writeFileSync(CACHE_FILE, JSON.stringify(newCache, null, 2));
    } else {
        fs.writeFileSync(CACHE_FILE, JSON.stringify(cache, null, 2));
    }
}

function getUserData(phoneNumber) {
    if (!fs.existsSync(WAIT_JSON_FILE)) return { username: "unknown", user_id: null };
    try {
        const waitList = JSON.parse(fs.readFileSync(WAIT_JSON_FILE));
        const cleanTarget = phoneNumber.replace(/[^\d]/g, '');
        for (const entry of waitList) {
            const cleanEntry = String(entry.number || "").replace(/[^\d]/g, '');
            if (cleanTarget === cleanEntry) return { username: entry.username || "unknown", user_id: entry.user_id };
        }
    } catch (e) {}
    return { username: "unknown", user_id: null };
}

function extractOtp(text) {
    if (!text) return null;
    const patterns = [/(\d{3}[\s-]\d{3})/, /(?:code|otp|kode)[:\s]*([\d\s-]+)/i, /\b(\d{4,8})\b/];
    for (const p of patterns) {
        const m = text.match(p);
        if (m) {
            const otp = (m[1] || m[0]).replace(/[^\d]/g, '');
            if (otp.length >= 4) return otp;
        }
    }
    return null;
}

function maskPhone(phone) {
    const digits = phone.replace(/[^\d]/g, '');
    if (digits.length < 7) return phone;
    return `+${digits.slice(0, 5)}***${digits.slice(-4)}`;
}

async function sendTelegram(text, otpCode = null, targetChat = CHAT_ID) {
    const url = `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`;
    const payload = { chat_id: targetChat, text, parse_mode: 'HTML', disable_web_page_preview: true };

    if (otpCode) {
        payload.reply_markup = {
            inline_keyboard: [
                [{ text: `📑 Copy OTP: ${otpCode}`, callback_data: `copy_${otpCode}` }, { text: "🎭 Owner", url: TELEGRAM_ADMIN_LINK }],
                [{ text: "📞 Get Number", url: TELEGRAM_BOT_LINK }]
            ]
        };
    }
    try { await axios.post(url, payload); } catch (e) { console.error(`❌ [MESSAGE] TG Error`); }
}

// ==================== MONITORING LOGIC ====================

async function startSmsMonitor() {
    console.log("🚀 [MESSAGE] SMS Monitor Service Starting...");

    const checkState = setInterval(() => {
        if (state.browser || process.env.WS_ENDPOINT) {
            clearInterval(checkState);
            console.log("✅ [MESSAGE] Browser Linked. Monitoring OTP on Tab 3...");
            runMonitoringLoop();
        }
    }, 5000);

    async function runMonitoringLoop() {
        while (true) {
            try {
                if (!monitorPage || monitorPage.isClosed()) {
                    monitorPage = await getSharedPage();
                    if (!monitorPage) {
                        await new Promise(r => setTimeout(r, 5000));
                        continue;
                    }
                    // Gak butuh gambar untuk monitor API
                    await monitorPage.route('**/*.{png,jpg,jpeg,gif,svg}', route => route.abort());
                }

                if (!monitorPage.url().includes('/getnum')) {
                    await monitorPage.goto(DASHBOARD_URL, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {});
                }

                // --- INTERSEPSI API INFO ---
                const responsePromise = monitorPage.waitForResponse(r => r.url().includes("/getnum/info"), { timeout: 15000 }).catch(() => null);
                
                // Klik header untuk maksa StexSMS panggil API /getnum/info
                await monitorPage.click('th:has-text("Number Info")', { force: true }).catch(() => {});
                
                const response = await responsePromise;
                if (response) {
                    const json = await response.json();
                    const numbers = json?.data?.numbers || [];

                    for (const item of numbers) {
                        // Cek status success dan ada pesan
                        if (item.status === 'success' && item.message) {
                            const otp = extractOtp(item.message);
                            const phone = "+" + item.number;
                            const key = `${otp}_${phone}`; 
                            const cache = getCache();

                            if (otp && !cache[key]) {
                                cache[key] = { t: Date.now() };
                                saveToCache(cache);

                                console.log(`✨ [MESSAGE] OTP FOUND: ${otp} | ${phone}`);

                                const user = getUserData(phone);
                                const userTag = user.username !== "unknown" ? user.username : "User";
                                const emoji = getCountryEmoji(item.country || "");
                                
                                const msg = `💭 <b>New Message Received</b>\n\n` +
                                            `<b>👤 User:</b> ${userTag}\n` +
                                            `<b>☎️ Number:</b> <code>${maskPhone(phone)}</code>\n` +
                                            `<b>🌍 Country:</b> <b>${item.country || "N/A"} ${emoji}</b>\n` +
                                            `<b>📪 Service:</b> <b>${item.full_number || "N/A"}</b>\n\n` +
                                            `🔐 OTP: <code>${otp}</code>\n\n` +
                                            `<b>FULL MESSAGE:</b>\n` +
                                            `<blockquote>${escapeHtml(item.message)}</blockquote>`;
                                
                                // Kirim ke grup dan ke User jika ID ketemu
                                await sendTelegram(msg, otp);
                                if (user.user_id) {
                                    await sendTelegram(msg, otp, user.user_id);
                                }

                                let log = [];
                                if (fs.existsSync(SMC_JSON_FILE)) try { log = JSON.parse(fs.readFileSync(SMC_JSON_FILE)); } catch(e){}
                                log.push({ service: item.full_number, number: phone, otp, message: item.message, time: new Date().toLocaleString() });
                                fs.writeFileSync(SMC_JSON_FILE, JSON.stringify(log.slice(-50), null, 2));
                            }
                        }
                    }
                }
            } catch (e) {
                console.error(`❌ [MESSAGE] Loop Error: ${e.message}`);
                if (monitorPage) await monitorPage.close().catch(() => {});
                monitorPage = null;
                await new Promise(r => setTimeout(r, 10000));
            }
            // Delay 8 detik antar request biar gak kena limit Cloudflare StexSMS
            await new Promise(r => setTimeout(r, 8000)); 
        }
    }
}

startSmsMonitor();
