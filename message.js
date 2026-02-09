const axios = require('axios');
const fs = require('fs');
const path = require('path');
// --- MENGGUNAKAN SHARED BROWSER ---
const { getNewPage } = require('./browser-shared'); 

// ================= KONFIGURASI =================
const BOT_TOKEN = "7562117237:AAFQnb5aCmeSHHi_qAJz3vkoX4HbNGohe38";
const CHAT_ID = "-1003492226491"; 
const ADMIN_ID = "7184123643";
const TELEGRAM_BOT_LINK = "https://t.me/newgettbot";
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

let totalSent = 0;
let lastUpdateId = 0;
const startTime = Date.now();
let monitorPage = null;

// ================= UTILS =================

const escapeHtml = (text) => (text ? text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") : "");
const getCountryEmoji = (c) => (COUNTRY_EMOJI[c?.trim().toUpperCase()] || "🏴‍☠️");

function getCache() {
    if (fs.existsSync(CACHE_FILE)) {
        try { return JSON.parse(fs.readFileSync(CACHE_FILE)); } catch (e) { return {}; }
    }
    return {};
}

function saveToCache(cache) {
    // Bersihkan cache jika terlalu besar (> 500 entry) agar file tidak bengkak
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
                [{ text: ` Copy OTP: ${otpCode}`, copy_text: { text: otpCode } }, { text: "🎭 Owner", url: TELEGRAM_ADMIN_LINK }],
                [{ text: "📞 Get Number", url: TELEGRAM_BOT_LINK }]
            ]
        };
    }
    try { await axios.post(url, payload); } catch (e) { console.error(`❌ [MESSAGE] TG Error: ${e.message}`); }
}

// ================= COMMAND HANDLERS =================

async function checkTelegramCommands() {
    try {
        const resp = await axios.get(`https://api.telegram.org/bot${BOT_TOKEN}/getUpdates?offset=${lastUpdateId + 1}&timeout=1`);
        if (resp.data?.result) {
            for (const u of resp.data.result) {
                lastUpdateId = u.update_id;
                const m = u.message;
                if (!m || String(m.from.id) !== String(ADMIN_ID)) continue;

                if (m.text === "/status") {
                    const uptime = Math.floor((Date.now() - startTime) / 1000);
                    const msg = `🤖 <b>Zura Message Status</b>\n⚡ Live: ✅\nUptime: <code>${Math.floor(uptime/3600)}h ${Math.floor((uptime%3600)/60)}m</code>\nTotal OTP: <b>${totalSent}</b>`;
                    await sendTelegram(msg, null, ADMIN_ID);
                }
            }
        }
    } catch (e) {}
}

// ================= MONITORING LOGIC =================

async function startSmsMonitor() {
    console.log("🟢 [MESSAGE] Service Background Active (API Intercept Mode).");

    while (true) {
        try {
            if (!monitorPage || monitorPage.isClosed()) {
                monitorPage = await getNewPage();
                console.log("[MESSAGE] Tab baru berhasil dibuat.");
            }

            if (!monitorPage.url().includes('/getnum')) {
                await monitorPage.goto(DASHBOARD_URL, { waitUntil: 'domcontentloaded' });
            }

            // Pemicu refresh data dengan cara halus (intersepsi API)
            const responsePromise = monitorPage.waitForResponse(r => r.url().includes("/getnum/info"), { timeout: 5000 }).catch(() => null);
            await monitorPage.click('th:has-text("Number Info")', { force: true }).catch(() => {});
            
            const response = await responsePromise;
            if (response) {
                const json = await response.json();
                const numbers = json?.data?.numbers || [];

                for (const item of numbers) {
                    // Cek status dan pesan
                    if (item.status === 'success' && item.message) {
                        const otp = extractOtp(item.message);
                        const phone = "+" + item.number;
                        const key = `${otp}_${phone}`;
                        const cache = getCache();

                        if (otp && !cache[key]) {
                            cache[key] = { t: Date.now() };
                            saveToCache(cache);

                            console.log(`✨ [MESSAGE] OTP Found: ${otp} for ${phone}`);

                            const user = getUserData(phone);
                            const userTag = user.username !== "unknown" ? `@${user.username}` : "unknown";
                            const emoji = getCountryEmoji(item.country || "");
                            
                            const msg = `💭 <b>New Message Received</b>\n\n` +
                                        `<b>👤 User:</b> ${userTag}\n` +
                                        `<b>☎️ Number:</b> <code>${maskPhone(phone)}</code>\n` +
                                        `<b>🌍 Country:</b> <b>${item.country || "N/A"} ${emoji}</b>\n` +
                                        `<b>📪 Service:</b> <b>${item.full_number || "N/A"}</b>\n\n` +
                                        `🔐 OTP: <code>${otp}</code>\n\n` +
                                        `<b>FULL MESSAGE:</b>\n` +
                                        `<blockquote>${escapeHtml(item.message)}</blockquote>`;
                            
                            await sendTelegram(msg, otp);
                            totalSent++;

                            // Simpan log lokal
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
        }
        
        await checkTelegramCommands();
        await new Promise(r => setTimeout(r, 8000)); // Cek setiap 8 detik
    }
}

// Langsung eksekusi karena di-fork oleh main.js
startSmsMonitor();
