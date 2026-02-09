const axios = require('axios');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const { state } = require('./helpers/state'); 

const CONFIG = {
    BOT_TOKEN: "8264103317:AAG_-LZQIxrMDIlLlttWQqIvA9xu_GNMwnc",
    CHAT_ID: "-1003358198353",
    DASHBOARD_URL: "https://stexsms.com/mdashboard/console",
    ALLOWED_SERVICES: ['whatsapp', 'facebook'],
    BANNED_COUNTRIES: ['angola'],
    SEND_DELAY: 2000 
};

let SENT_MESSAGES = new Map();
let CACHE_SET = new Set();
let MESSAGE_QUEUE = []; 
let IS_PROCESSING_QUEUE = false; 
const INLINE_JSON_PATH = path.join(__dirname, 'inline.json');

let COUNTRY_EMOJI = {};
try { COUNTRY_EMOJI = require('./country.json'); } catch (e) {}

const getCountryEmoji = (name) => (name ? (COUNTRY_EMOJI[name.toUpperCase()] || "🏴‍☠️") : "🏴‍☠️");
const cleanPhoneNumber = (p) => (p ? p.replace(/[^0-9X]/g, '') : "N/A");
const cleanServiceName = (s) => {
    if (!s) return "Unknown";
    const low = s.toLowerCase();
    return low.includes('facebook') ? 'Facebook' : low.includes('whatsapp') ? 'WhatsApp' : s.trim();
};

const formatLiveMessage = (rangeVal, count, country, service, msg) => {
    const emoji = getCountryEmoji(country);
    const header = count > 1 ? `<code>${rangeVal}</code> (${count}x)` : `<code>${rangeVal}</code>`;
    const escaped = msg.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return `🌤️<b>Live message new range</b>\n\n☎️Range    : ${header}\n${emoji} Country : ${country}\n📪 Service : ${service}\n\n🗯️Message Available :\n<blockquote>${escaped}</blockquote>`;
};

async function getSharedPage() {
    try {
        const wsAddr = process.env.WS_ENDPOINT || state.wsEndpoint;
        const browser = await chromium.connect(wsAddr);
        const context = browser.contexts()[0];
        if (!context) return null;
        
        // Pastikan buka tab BARU, bukan pake tab yang lama
        const page = await context.newPage();
        console.log("📍 [RANGE] Berhasil buka Tab Baru untuk Console.");
        return page;
    } catch (e) {
        console.error("❌ [RANGE] Gagal buka tab:", e.message);
        return null;
    }
}

async function monitorTask() {
    console.log("🚀 [RANGE] Service Background Active (Wait for Browser...)");
    
    // Tunggu sampai main.js siap
    while (!(state.browser || process.env.WS_ENDPOINT)) {
        await new Promise(r => setTimeout(r, 2000));
    }

    console.log("✅ [RANGE] Browser Linked. Monitoring Tab Console...");
    let page = null;

    while (true) {
        try {
            if (!page || page.isClosed()) {
                page = await getSharedPage();
                if (!page) { await new Promise(r => setTimeout(r, 5000)); continue; }
                await page.route('**/*.{png,jpg,jpeg,gif,svg}', r => r.abort());
            }

            // Navigasi dengan timeout lebih lama
            if (!page.url().includes('/console')) {
                await page.goto(CONFIG.DASHBOARD_URL, { waitUntil: 'load', timeout: 60000 });
                console.log("📍 [RANGE] Navigasi ke Console sukses.");
            }

            const CONSOLE_SELECTOR = ".group.flex.flex-col.sm\\:flex-row.sm\\:items-start.gap-3.p-3.rounded-lg";
            await page.waitForSelector(CONSOLE_SELECTOR, { timeout: 15000 }).catch(() => {});
            const elements = await page.locator(CONSOLE_SELECTOR).all();

            for (const el of elements) {
                try {
                    const rawC = await el.locator(".flex-shrink-0 .text-\\[10px\\].text-slate-600.mt-1.font-mono").innerText();
                    const country = rawC.includes("•") ? rawC.split("•")[1].trim() : "Unknown";
                    if (CONFIG.BANNED_COUNTRIES.includes(country.toLowerCase())) continue;

                    const service = cleanServiceName(await el.locator(".text-blue-400").innerText());
                    if (!CONFIG.ALLOWED_SERVICES.some(s => service.toLowerCase().includes(s))) continue;

                    const phone = cleanPhoneNumber(await el.locator(".font-mono").last().innerText());
                    const fullMessage = (await el.locator("p").innerText()).replace('➜', '').trim();

                    if (phone.includes('XXX')) {
                        const cacheKey = `${phone}_${fullMessage.slice(0, 15)}`; 
                        if (!CACHE_SET.has(cacheKey)) {
                            CACHE_SET.add(cacheKey);
                            const cur = SENT_MESSAGES.get(phone) || { count: 0 };
                            MESSAGE_QUEUE.push({ 
                                rangeVal: phone, country, service, count: cur.count + 1, 
                                text: formatLiveMessage(phone, cur.count + 1, country, service, fullMessage) 
                            });
                            // Panggil proses antrean
                            if (!IS_PROCESSING_QUEUE) processQueue();
                        }
                    }
                } catch (e) {}
            }
        } catch (err) { 
            console.error("❌ [RANGE] Loop Error:", err.message);
            page = null; 
        }
        await new Promise(r => setTimeout(r, 15000));
    }
}

// Tambahin fungsi antrean dan save ke json biar komplit
async function processQueue() {
    IS_PROCESSING_QUEUE = true;
    while (MESSAGE_QUEUE.length > 0) {
        const item = MESSAGE_QUEUE.shift();
        try {
            await axios.post(`https://api.telegram.org/bot${CONFIG.BOT_TOKEN}/sendMessage`, {
                chat_id: CONFIG.CHAT_ID, text: item.text, parse_mode: 'HTML',
                reply_markup: { inline_keyboard: [[{ text: "📞 Get Number", url: "https://t.me/myzuraisgoodbot" }]] }
            });
            SENT_MESSAGES.set(item.rangeVal, { count: item.count, timestamp: Date.now() });
        } catch (e) {}
        await new Promise(r => setTimeout(r, CONFIG.SEND_DELAY));
    }
    IS_PROCESSING_QUEUE = false;
}

monitorTask();
