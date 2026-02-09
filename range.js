const axios = require('axios');
const fs = require('fs');
const path = require('path');
// Mengambil fungsi dari shared browser yang sudah di-init di main.js
const { getNewPage } = require('./browser-shared'); 

// ==================== KONFIGURASI ====================
const CONFIG = {
    BOT_TOKEN: "8264103317:AAG_-LZQIxrMDIlLlttWQqIvA9xu_GNMwnc",
    CHAT_ID: "-1003358198353",
    DASHBOARD_URL: "https://stexsms.com/mdashboard/console",
    ALLOWED_SERVICES: ['whatsapp', 'facebook'],
    BANNED_COUNTRIES: ['angola'],
    SEND_DELAY: 1500 
};

// ==================== GLOBAL VARIABLES ====================
let SENT_MESSAGES = new Map();
let CACHE_SET = new Set();
let MESSAGE_QUEUE = []; 
let IS_PROCESSING_QUEUE = false; 

let COUNTRY_EMOJI = {};
try {
    COUNTRY_EMOJI = require('./country.json');
} catch (e) {
    console.error("⚠️ [RANGE] country.json missing.");
}

const INLINE_JSON_PATH = path.join(__dirname, 'inline.json');

// --- UTILITY ---
const getCountryEmoji = (name) => (name ? (COUNTRY_EMOJI[name.toUpperCase()] || "🏴‍☠️") : "🏴‍☠️");
const cleanPhoneNumber = (p) => (p ? p.replace(/[^0-9X]/g, '') : "N/A");
const cleanServiceName = (s) => {
    if (!s) return "Unknown";
    const low = s.toLowerCase();
    if (low.includes('facebook')) return 'Facebook';
    if (low.includes('whatsapp')) return 'WhatsApp';
    return s.trim();
};

const formatLiveMessage = (rangeVal, count, country, service, msg) => {
    const emoji = getCountryEmoji(country);
    const header = count > 1 ? `<code>${rangeVal}</code> (${count}x)` : `<code>${rangeVal}</code>`;
    const escaped = msg.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

    return `🌤️Live message new range\n\n` +
           `☎️Range    : ${header}\n` +
           `${emoji} Country : ${country}\n` +
           `📪 Service : ${service}\n\n` +
           `🗯️Message Available :\n` +
           `<blockquote>${escaped}</blockquote>`;
};

const saveToInlineJson = (rangeVal, country, service) => {
    const sMap = { 'whatsapp': 'WA', 'facebook': 'FB' };
    const shortS = sMap[service.toLowerCase()] || service.substring(0, 5).toUpperCase();
    try {
        let list = [];
        if (fs.existsSync(INLINE_JSON_PATH)) list = JSON.parse(fs.readFileSync(INLINE_JSON_PATH, 'utf-8'));
        if (list.some(i => i.range === rangeVal)) return;
        list.push({ range: rangeVal, country: country.toUpperCase(), emoji: getCountryEmoji(country), service: shortS });
        if (list.length > 20) list = list.slice(-20);
        fs.writeFileSync(INLINE_JSON_PATH, JSON.stringify(list, null, 2));
    } catch (e) { console.error("❌ [RANGE] Save Inline Error"); }
};

// ==================== QUEUE SYSTEM ====================
async function processQueue() {
    if (IS_PROCESSING_QUEUE || MESSAGE_QUEUE.length === 0) return;
    IS_PROCESSING_QUEUE = true;
    while (MESSAGE_QUEUE.length > 0) {
        const item = MESSAGE_QUEUE.shift();
        try {
            if (SENT_MESSAGES.has(item.rangeVal)) {
                const old = SENT_MESSAGES.get(item.rangeVal);
                await axios.post(`https://api.telegram.org/bot${CONFIG.BOT_TOKEN}/deleteMessage`, {
                    chat_id: CONFIG.CHAT_ID, message_id: old.message_id
                }).catch(() => {});
            }
            const res = await axios.post(`https://api.telegram.org/bot${CONFIG.BOT_TOKEN}/sendMessage`, {
                chat_id: CONFIG.CHAT_ID, text: item.text, parse_mode: 'HTML',
                reply_markup: { inline_keyboard: [[{ text: "📞 Get Number", url: "https://t.me/newgettbot" }]] }
            });
            if (res.data.ok) {
                SENT_MESSAGES.set(item.rangeVal, { message_id: res.data.result.message_id, count: item.count, timestamp: Date.now() });
                saveToInlineJson(item.rangeVal, item.country, item.service);
                console.log(`🚀 [RANGE] SENT: ${item.rangeVal}`);
            }
        } catch (e) { console.error("❌ [RANGE] TG Error"); }
        await new Promise(r => setTimeout(r, CONFIG.SEND_DELAY));
    }
    IS_PROCESSING_QUEUE = false;
}

// ==================== MONITOR LOGIC ====================
async function monitorTask() {
    console.log("🟢 [RANGE] Service Background Active.");
    let page = null;

    while (true) {
        try {
            if (!page || page.isClosed()) page = await getNewPage();
            if (page.url() !== CONFIG.DASHBOARD_URL) await page.goto(CONFIG.DASHBOARD_URL, { waitUntil: 'domcontentloaded' });

            const CONSOLE_SELECTOR = ".group.flex.flex-col.sm\\:flex-row.sm\\:items-start.gap-3.p-3.rounded-lg";
            await page.waitForSelector(CONSOLE_SELECTOR, { timeout: 10000 }).catch(() => {});
            const elements = await page.locator(CONSOLE_SELECTOR).all();

            for (const el of elements) {
                try {
                    const rawC = await el.locator(".flex-shrink-0 .text-\\[10px\\].text-slate-600.mt-1.font-mono").innerText();
                    const country = rawC.includes("•") ? rawC.split("•")[1].trim() : "Unknown";
                    if (CONFIG.BANNED_COUNTRIES.includes(country.toLowerCase())) continue;

                    const sRaw = await el.locator(".flex-grow.min-w-0 .text-xs.font-bold.text-blue-400").innerText();
                    const service = cleanServiceName(sRaw);
                    if (!CONFIG.ALLOWED_SERVICES.some(s => service.toLowerCase().includes(s))) continue;

                    const phoneRaw = await el.locator(".flex-grow.min-w-0 .text-\\[10px\\].font-mono").last().innerText();
                    const phone = cleanPhoneNumber(phoneRaw);
                    const msgRaw = await el.locator(".flex-grow.min-w-0 p").innerText();
                    const fullMessage = msgRaw.replace('➜', '').trim();

                    const cacheKey = `${phone}_${fullMessage.length}`;
                    if (phone.includes('XXX') && !CACHE_SET.has(cacheKey)) {
                        CACHE_SET.add(cacheKey);
                        if (CACHE_SET.size > 1000) CACHE_SET.delete(CACHE_SET.values().next().value);
                        const cur = SENT_MESSAGES.get(phone) || { count: 0 };
                        const newCount = cur.count + 1;
                        MESSAGE_QUEUE.push({ rangeVal: phone, country, service, count: newCount, text: formatLiveMessage(phone, newCount, country, service, fullMessage) });
                        processQueue();
                    }
                } catch (e) {}
            }
            // Memory Cleanup (30 min)
            const now = Date.now();
            for (let [r, v] of SENT_MESSAGES.entries()) if (now - v.timestamp > 1800000) SENT_MESSAGES.delete(r);
        } catch (err) {
            console.error(`❌ [RANGE] Loop Error: ${err.message}`);
            if (page) await page.close().catch(() => {});
            page = null;
        }
        await new Promise(r => setTimeout(r, 15000));
    }
}

// Langsung eksekusi monitoring
monitorTask();
