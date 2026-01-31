const fs = require('fs');
const path = require('path');
const axios = require('axios');
const { chromium } = require('playwright');
const { Mutex } = require('async-mutex');
const cron = require('node-cron');
const dotenv = require('dotenv');
const { fork } = require('child_process');

// Load Env
dotenv.config();

// Load Configs
const HEADLESS_CONFIG = require('./headless.js');
const GLOBAL_COUNTRY_EMOJI = require('./country.json');

// --- KONFIGURASI DAN VARIABEL GLOBAL ---
const BOT_TOKEN = process.env.BOT_TOKEN;
const API = `https://api.telegram.org/bot${BOT_TOKEN}`;
const GROUP_ID_1 = parseInt(process.env.GROUP_ID_1);
const GROUP_ID_2 = parseInt(process.env.GROUP_ID_2);
const ADMIN_ID = parseInt(process.env.ADMIN_ID);
const STEX_EMAIL = process.env.STEX_EMAIL;
const STEX_PASSWORD = process.env.STEX_PASSWORD;

if (!BOT_TOKEN || !GROUP_ID_1 || !GROUP_ID_2 || !ADMIN_ID || !STEX_EMAIL || !STEX_PASSWORD) {
    console.error("[FATAL] Variabel lingkungan .env belum lengkap.");
    process.exit(1);
}

const LOGIN_URL = "https://stexsms.com/mauth/login";
const TARGET_URL = "https://stexsms.com/mdashboard/getnum";
const BOT_USERNAME_LINK = "https://t.me/myzuraisgoodbot";
const GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1";
const GROUP_LINK_2 = "https://t.me/zura14g";

const OTP_PRICE = 0.003500;
const MIN_WD_AMOUNT = 1.000000;

// Files
const USER_FILE = "user.json";
const CACHE_FILE = "cache.json";
const INLINE_RANGE_FILE = "inline.json";
const WAIT_FILE = "wait.json";
const AKSES_GET10_FILE = "aksesget10.json";
const PROFILE_FILE = "profile.json";

// Locks & State
const playwrightLock = new Mutex();
let browser = null;
let sharedPage = null;

// Global State Sets/Maps
let waitingBroadcastInput = new Set();
let broadcastMessage = {};
let verifiedUsers = new Set();
let waitingAdminInput = new Set();
let manualRangeInput = new Set();
let get10RangeInput = new Set();
let waitingDanaInput = new Set();
let pendingMessage = {};
let lastUsedRange = {};

// Progress Bar Config
const MAX_BAR_LENGTH = 12;
const FILLED_CHAR = "█";
const EMPTY_CHAR = "░";

const STATUS_MAP = {
    0: "Menunggu di antrian sistem aktif..",
    3: "Mengirim permintaan nomor baru go.",
    4: "Memulai pencarian di tabel data..",
    5: "Mencari nomor pada siklus satu run",
    8: "Mencoba ulang pada siklus dua wait",
    12: "Nomor ditemukan memproses data fin"
};

// ==============================================================================
// FUNGSI UTILITAS MANAJEMEN FILE
// ==============================================================================

function loadJson(filename, defaultVal = []) {
    if (fs.existsSync(filename)) {
        try {
            return JSON.parse(fs.readFileSync(filename, 'utf8'));
        } catch (e) {
            return defaultVal;
        }
    }
    return defaultVal;
}

function saveJson(filename, data) {
    fs.writeFileSync(filename, JSON.stringify(data, null, 2));
}

function loadUsers() {
    return new Set(loadJson(USER_FILE, []));
}

function saveUsers(userId) {
    const users = loadUsers();
    if (!users.has(userId)) {
        users.add(userId);
        saveJson(USER_FILE, Array.from(users));
    }
}

function loadCache() { return loadJson(CACHE_FILE, []); }

function saveCache(entry) {
    const cache = loadCache();
    if (cache.length >= 1000) cache.shift();
    cache.push(entry);
    saveJson(CACHE_FILE, cache);
}

function normalizeNumber(number) {
    let norm = String(number).trim().replace(/[\s-]/g, "");
    if (!norm.startsWith('+') && /^\d+$/.test(norm)) {
        norm = '+' + norm;
    }
    return norm;
}

function isInCache(number) {
    const cache = loadCache();
    const norm = normalizeNumber(number);
    return cache.some(entry => normalizeNumber(entry.number) === norm);
}

function loadInlineRanges() { return loadJson(INLINE_RANGE_FILE, []); }
function saveInlineRanges(ranges) { saveJson(INLINE_RANGE_FILE, ranges); }

function loadAksesGet10() { return new Set(loadJson(AKSES_GET10_FILE, [])); }
function saveAksesGet10(userId) {
    const akses = loadAksesGet10();
    akses.add(parseInt(userId));
    saveJson(AKSES_GET10_FILE, Array.from(akses));
}
function hasGet10Access(userId) {
    if (userId === ADMIN_ID) return true;
    return loadAksesGet10().has(parseInt(userId));
}

function loadProfiles() { return loadJson(PROFILE_FILE, {}); }
function saveProfiles(data) { saveJson(PROFILE_FILE, data); }

function getUserProfile(userId, firstName = "User") {
    const profiles = loadProfiles();
    const strId = String(userId);
    const today = new Date().toISOString().split('T')[0];

    if (!profiles[strId]) {
        profiles[strId] = {
            name: firstName,
            dana: "Belum Diset",
            dana_an: "Belum Diset",
            balance: 0.000000,
            otp_semua: 0,
            otp_hari_ini: 0,
            last_active: today
        };
        saveProfiles(profiles);
    } else {
        if (profiles[strId].name !== firstName) {
            profiles[strId].name = firstName;
            saveProfiles(profiles);
        }
        if (profiles[strId].last_active !== today) {
            profiles[strId].otp_hari_ini = 0;
            profiles[strId].last_active = today;
            saveProfiles(profiles);
        }
    }
    return profiles[strId];
}

function updateUserDana(userId, danaNumber, danaName) {
    const profiles = loadProfiles();
    const strId = String(userId);
    if (profiles[strId]) {
        profiles[strId].dana = danaNumber;
        profiles[strId].dana_an = danaName;
        saveProfiles(profiles);
        return true;
    }
    return false;
}

function loadWaitList() { return loadJson(WAIT_FILE, []); }
function saveWaitList(data) { saveJson(WAIT_FILE, data); }

function addToWaitList(number, userId, username, firstName) {
    let waitList = loadWaitList();
    const norm = normalizeNumber(number);
    let identity = username ? `@${username.replace('@', '')}` : `<a href="tg://user?id=${userId}">${firstName}</a>`;
    
    // Remove existing
    waitList = waitList.filter(item => item.number !== norm);
    
    waitList.push({
        number: norm,
        user_id: userId,
        username: identity,
        timestamp: Date.now() / 1000
    });
    saveWaitList(waitList);
}

function getProgressMessage(currentStep, totalSteps, prefixRange, numCount) {
    const progressRatio = Math.min(currentStep / 12, 1.0);
    const filledCount = Math.ceil(progressRatio * MAX_BAR_LENGTH);
    const emptyCount = MAX_BAR_LENGTH - filledCount;
    const bar = FILLED_CHAR.repeat(filledCount) + EMPTY_CHAR.repeat(emptyCount);

    let status = STATUS_MAP[currentStep];
    if (!status) {
        if (currentStep < 3) status = STATUS_MAP[0];
        else if (currentStep < 5) status = STATUS_MAP[4];
        else if (currentStep < 8) status = STATUS_MAP[5];
        else if (currentStep < 12) status = STATUS_MAP[8];
        else status = STATUS_MAP[12];
    }

    return `<code>${status}</code>\n<blockquote>Range: <code>${prefixRange}</code> | Jumlah: <code>${numCount}</code></blockquote>\n<code>Load:</code> [${bar}]`;
}

function generateInlineKeyboard(ranges) {
    const keyboard = [];
    ranges.forEach(item => {
        const service = item.service || "WA";
        const text = `${item.emoji} ${item.country} ${service}`;
        const callbackData = `select_range:${item.range}`;
        keyboard.push([{ text: text, callback_data: callbackData }]);
    });
    keyboard.push([{ text: "INPUT MANUAL RANGE..🖊️", callback_data: "manual_range" }]);
    return { inline_keyboard: keyboard };
}

// ==============================================================================
// FUNGSI API TELEGRAM
// ==============================================================================

async function tgSend(chatId, text, replyMarkup = null) {
    const data = { chat_id: chatId, text: text, parse_mode: "HTML" };
    if (replyMarkup) data.reply_markup = replyMarkup;
    try {
        const res = await axios.post(`${API}/sendMessage`, data);
        if (res.data.ok) return res.data.result.message_id;
    } catch (e) {
        return null;
    }
    return null;
}

async function tgEdit(chatId, messageId, text, replyMarkup = null) {
    const data = { chat_id: chatId, message_id: messageId, text: text, parse_mode: "HTML" };
    if (replyMarkup) data.reply_markup = replyMarkup;
    try {
        await axios.post(`${API}/editMessageText`, data);
    } catch (e) { /* ignore */ }
}

async function tgDelete(chatId, messageId) {
    try {
        await axios.post(`${API}/deleteMessage`, { chat_id: chatId, message_id: messageId });
    } catch (e) { /* ignore */ }
}

async function tgSendAction(chatId, action = "typing") {
    try {
        await axios.post(`${API}/sendChatAction`, { chat_id: chatId, action: action });
    } catch (e) { /* ignore */ }
}

async function tgGetUpdates(offset) {
    try {
        const res = await axios.get(`${API}/getUpdates`, { params: { offset: offset, timeout: 5 } });
        return res.data;
    } catch (e) {
        return { ok: false, result: [] };
    }
}

async function isUserInGroup(userId, groupId) {
    try {
        const res = await axios.get(`${API}/getChatMember`, { params: { chat_id: groupId, user_id: userId } });
        if (!res.data.ok) return false;
        const status = res.data.result.status;
        return ["member", "administrator", "creator"].includes(status);
    } catch (e) {
        return false;
    }
}

async function isUserInBothGroups(userId) {
    const [g1, g2] = await Promise.all([
        isUserInGroup(userId, GROUP_ID_1),
        isUserInGroup(userId, GROUP_ID_2)
    ]);
    return g1 && g2;
}

async function tgBroadcast(messageText, adminId) {
    const userIds = Array.from(loadUsers());
    let success = 0;
    let fail = 0;
    
    let adminMsgId = await tgSend(adminId, `🔄 Memulai siaran ke **${userIds.length}** pengguna. Harap tunggu...`);

    for (let i = 0; i < userIds.length; i++) {
        const uid = userIds[i];
        if (i % 10 === 0 && adminMsgId) {
            await tgEdit(adminId, adminMsgId, `🔄 Siaran: **${i}/${userIds.length}** (Sukses: ${success}, Gagal: ${fail})`);
        }
        const res = await tgSend(uid, messageText);
        if (res) success++; else fail++;
        await new Promise(r => setTimeout(r, 50));
    }
    
    const report = `✅ Siaran Selesai!\n\n👥 Total Pengguna: <b>${userIds.length}</b>\n🟢 Berhasil Terkirim: <b>${success}</b>\n🔴 Gagal Terkirim: <b>${fail}</b>`;
    if (adminMsgId) await tgEdit(adminId, adminMsgId, report);
    else await tgSend(adminId, report);
}

// ==============================================================================
// BROWSER & PLAYWRIGHT LOGIC
// ==============================================================================

async function initBrowser() {
    if (browser) {
        try { await browser.close(); } catch(e){}
    }
    
    console.log("[BROWSER] Launching Chromium...");
    browser = await chromium.launch({
        headless: HEADLESS_CONFIG.headless,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const context = await browser.newContext();
    sharedPage = await context.newPage();

    console.log("[BROWSER] Logging in...");
    try {
        await sharedPage.goto(LOGIN_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
        
        // Login Flow
        await sharedPage.fill("input[name='email']", STEX_EMAIL); 
        await sharedPage.fill("input[name='password']", STEX_PASSWORD);
        
        // Cari tombol login, sesuaikan selector jika perlu
        const loginBtn = sharedPage.locator("button[type='submit']");
        if (await loginBtn.isVisible()) {
            await loginBtn.click();
        } else {
             // Fallback kalau selector beda
             await sharedPage.keyboard.press('Enter');
        }

        await sharedPage.waitForURL('**/mdashboard/**', { timeout: 60000 });
        console.log("[BROWSER] Login Success. Redirecting to GetNum...");
        
        await sharedPage.goto(TARGET_URL, { waitUntil: 'domcontentloaded' });
        console.log("[BROWSER] Ready on Target URL.");

    } catch (e) {
        console.error(`[BROWSER ERROR] Login Failed: ${e.message}`);
        // Retry logic could go here
    }
}

async function getNumberAndCountryFromRow(rowSelector, page) {
    try {
        const row = page.locator(rowSelector);
        if (!(await row.isVisible())) return null;

        const phoneEl = row.locator("td:nth-child(1) span.font-mono");
        const numberRawList = await phoneEl.allInnerTexts();
        const numberRaw = numberRawList.length > 0 ? numberRawList[0].trim() : null;
        
        const number = numberRaw ? normalizeNumber(numberRaw) : null;
        if (!number || isInCache(number)) return null;

        const statusEl = row.locator("td:nth-child(1) div:nth-child(2) span");
        const statusTextList = await statusEl.allInnerTexts();
        const statusText = statusTextList.length > 0 ? statusTextList[0].trim().toLowerCase() : "unknown";

        if (statusText.includes("success") || statusText.includes("failed")) return null;

        const countryEl = row.locator("td:nth-child(2) span.text-slate-200");
        const countryList = await countryEl.allInnerTexts();
        const country = countryList.length > 0 ? countryList[0].trim().toUpperCase() : "UNKNOWN";

        if (number && number.length > 5) return { number, country, status: statusText };
        return null;

    } catch (e) {
        return null;
    }
}

async function getAllNumbersParallel(page, numToFetch) {
    const tasks = [];
    for (let i = 1; i <= numToFetch + 5; i++) {
        tasks.push(getNumberAndCountryFromRow(`tbody tr:nth-child(${i})`, page));
    }
    const results = await Promise.all(tasks);
    
    const currentNumbers = [];
    const seen = new Set();
    
    for (const res of results) {
        if (res && res.number && !seen.has(res.number)) {
            currentNumbers.push(res);
            seen.add(res.number);
        }
    }
    return currentNumbers;
}

async function actionTask(userId) {
    const interval = setInterval(() => {
        tgSendAction(userId, "typing");
    }, 4500);
    return interval;
}

async function processUserInput(userId, prefix, clickCount, usernameTg, firstNameTg, messageIdToEdit = null) {
    let msgId = messageIdToEdit || pendingMessage[userId];
    let actionInterval = null;
    const numToFetch = clickCount;

    if (playwrightLock.isLocked()) {
        if (!msgId) {
            msgId = await tgSend(userId, getProgressMessage(0, 0, prefix, numToFetch));
            if (!msgId) return;
        } else {
            await tgEdit(userId, msgId, getProgressMessage(0, 0, prefix, numToFetch));
        }
    }

    const release = await playwrightLock.acquire();
    try {
        actionInterval = await actionTask(userId);
        let currentStep = 0;
        const startOpTime = Date.now() / 1000;

        if (!msgId) {
            msgId = await tgSend(userId, getProgressMessage(currentStep, 0, prefix, numToFetch));
            if (!msgId) return;
        }

        // Re-check Page
        if (!sharedPage || sharedPage.isClosed()) {
             await initBrowser();
        }

        const INPUT_SELECTOR = "input[name='numberrange']";
        try {
            await sharedPage.waitForSelector(INPUT_SELECTOR, { state: 'visible', timeout: 10000 });
            await sharedPage.fill(INPUT_SELECTOR, "");
            await sharedPage.fill(INPUT_SELECTOR, prefix);
            
            currentStep = 1;
            await new Promise(r => setTimeout(r, 500));
            currentStep = 2;

            const BUTTON_SELECTOR = "button:has-text('Get Number')";
            await sharedPage.waitForSelector(BUTTON_SELECTOR, { state: 'visible', timeout: 10000 });

            for (let i = 0; i < clickCount; i++) {
                await sharedPage.click(BUTTON_SELECTOR, { force: true });
            }

            currentStep = 3;
            await tgEdit(userId, msgId, getProgressMessage(currentStep, 0, prefix, numToFetch));

            await new Promise(r => setTimeout(r, 500));
            currentStep = 4;
            await tgEdit(userId, msgId, getProgressMessage(currentStep, 0, prefix, numToFetch));

            await new Promise(r => setTimeout(r, 1000));

            const delayRound1 = 5.0;
            const delayRound2 = 5.0;
            const checkInterval = 0.25;
            let foundNumbers = [];

            const rounds = [delayRound1, delayRound2];

            for (let rIdx = 0; rIdx < rounds.length; rIdx++) {
                const duration = rounds[rIdx];
                if (rIdx === 0) currentStep = 5;
                else if (rIdx === 1) {
                    if (foundNumbers.length < numToFetch) {
                        await sharedPage.click(BUTTON_SELECTOR, { force: true });
                        await new Promise(r => setTimeout(r, 1500));
                        currentStep = 8;
                    }
                }

                const startTime = Date.now() / 1000;
                let lastCheck = 0;

                while ((Date.now() / 1000 - startTime) < duration) {
                    const now = Date.now() / 1000;
                    if (now - lastCheck >= checkInterval) {
                        foundNumbers = await getAllNumbersParallel(sharedPage, numToFetch);
                        lastCheck = now;
                        if (foundNumbers.length >= numToFetch) {
                            currentStep = 12;
                            break;
                        }
                    }

                    // Progress update
                    const elapsedTime = now - startOpTime;
                    const totalEstimated = delayRound1 + delayRound2 + 4;
                    const targetStep = Math.floor(12 * elapsedTime / totalEstimated);
                    if (targetStep > currentStep && targetStep <= 12) {
                        currentStep = targetStep;
                        await tgEdit(userId, msgId, getProgressMessage(currentStep, 0, prefix, numToFetch));
                    }
                    await new Promise(r => setTimeout(r, 50));
                }
                if (foundNumbers.length >= numToFetch) break;
            }

            if (!foundNumbers || foundNumbers.length === 0) {
                await tgEdit(userId, msgId, "❌ NOMOR TIDAK DI TEMUKAN. Coba lagi atau ganti range.");
                return;
            }

            const mainCountry = foundNumbers[0].country || "UNKNOWN";
            currentStep = 12;
            await tgEdit(userId, msgId, getProgressMessage(currentStep, 0, prefix, numToFetch));

            // Save Cache & Waitlist
            foundNumbers.forEach(entry => {
                saveCache({ number: entry.number, country: entry.country, user_id: userId, time: Date.now() });
                addToWaitList(entry.number, userId, usernameTg, firstNameTg);
            });

            lastUsedRange[userId] = prefix;
            const emoji = GLOBAL_COUNTRY_EMOJI[mainCountry] || "🗺️";
            
            let msg = "";
            if (numToFetch === 10) {
                msg = "✅The number is already.\n\n<code>";
                foundNumbers.slice(0, 10).forEach(entry => msg += `${entry.number}\n`);
                msg += "</code>";
            } else {
                msg = "✅ The number is ready\n\n";
                if (numToFetch === 1) {
                    msg += `📞 Number  : <code>${foundNumbers[0].number}</code>\n`;
                } else {
                    foundNumbers.slice(0, numToFetch).forEach((entry, idx) => {
                        msg += `📞 Number ${idx+1} : <code>${entry.number}</code>\n`;
                    });
                }
                msg += `${emoji} COUNTRY : ${mainCountry}\n` +
                       `🏷️ Range   : <code>${prefix}</code>\n\n` +
                       `<b>🤖 Number available please use, Waiting for OTP</b>\n`;
            }

            const inlineKb = {
                inline_keyboard: [
                    [{ text: "🔄 Change 1 Number", callback_data: `change_num:1:${prefix}` }],
                    [{ text: "🔄 Change 3 Number", callback_data: `change_num:3:${prefix}` }],
                    [{ text: "🔐 OTP Grup", url: GROUP_LINK_1 }, { text: "🌐 Change Range", callback_data: "getnum" }]
                ]
            };

            await tgEdit(userId, msgId, msg, inlineKb);

        } catch (e) {
            if (e.name === 'TimeoutError') {
                if (msgId) await tgEdit(userId, msgId, "❌ Timeout web. Web lambat atau tombol tidak ditemukan. Mohon coba lagi.");
            } else {
                if (msgId) await tgEdit(userId, msgId, `❌ Terjadi kesalahan fatal (${e.message}). Mohon coba lagi.`);
            }
        }

    } finally {
        if (actionInterval) clearInterval(actionInterval);
        release();
    }
}

// ==============================================================================
// TELEGRAM LOOP
// ==============================================================================

async function telegramLoop() {
    verifiedUsers = loadUsers();
    let offset = 0;

    // Bersihkan update lama
    await tgGetUpdates(-1);
    console.log("[TELEGRAM] Polling started...");

    while (true) {
        const data = await tgGetUpdates(offset);
        if (data && data.result) {
            for (const upd of data.result) {
                offset = upd.update_id + 1;

                // --- MESSAGE HANDLER ---
                if (upd.message) {
                    const msg = upd.message;
                    const chatId = msg.chat.id;
                    const userId = msg.from.id;
                    const firstName = msg.from.first_name || "User";
                    const usernameTg = msg.from.username;
                    const mention = usernameTg ? `@${usernameTg}` : `<a href='tg://user?id=${userId}'>${firstName}</a>`;
                    const text = msg.text || "";

                    // --- ADMIN COMMANDS ---
                    if (userId === ADMIN_ID) {
                        if (text.startsWith("/add")) {
                            waitingAdminInput.add(userId);
                            const prompt = "Silahkan kirim daftar range dalam format:\n\n<code>range > country > service</code>\nAtau default service WA:\n<code>range > country</code>\n\nContoh:\n<code>23273XXX > SIERRA LEONE > WA</code>";
                            const mid = await tgSend(userId, prompt);
                            if (mid) pendingMessage[userId] = mid;
                            continue;
                        } else if (text === "/info") {
                            waitingBroadcastInput.add(userId);
                            const mid = await tgSend(userId, "<b>Pesan Siaran</b>\n\nKirim pesan yang ingin disiarkan. Ketik <code>.batal</code> untuk batal.");
                            if (mid) broadcastMessage[userId] = mid;
                            continue;
                        } else if (text.startsWith("/get10akses ")) {
                            const targetId = text.split(" ")[1];
                            saveAksesGet10(targetId);
                            await tgSend(userId, `✅ User <code>${targetId}</code> berhasil diberi akses /get10.`);
                            continue;
                        } else if (text === "/list") {
                            const profiles = loadProfiles();
                            if (Object.keys(profiles).length === 0) {
                                await tgSend(userId, "❌ Belum ada data user.");
                            } else {
                                let msgList = "<b>📋 LIST SEMUA USER</b>\n\n";
                                let chunk = "";
                                let count = 0;
                                for (const [uid, pdata] of Object.entries(profiles)) {
                                    chunk += `👤 Name: ${pdata.name || 'Unknown'}\n🧾 Dana: ${pdata.dana || '-'}\n💰 Balance: $${(pdata.balance || 0).toFixed(6)}\n📊 Total OTP: ${pdata.otp_semua || 0}\n\n`;
                                    count++;
                                    if (count % 10 === 0) {
                                        await tgSend(userId, chunk);
                                        chunk = "";
                                        await new Promise(r => setTimeout(r, 500));
                                    }
                                }
                                if (chunk) await tgSend(userId, chunk);
                            }
                            continue;
                        }
                    }

                    // --- GET10 ---
                    if (text === "/get10") {
                        if (hasGet10Access(userId)) {
                            get10RangeInput.add(userId);
                            const mid = await tgSend(userId, "kirim range contoh 225071606XXX");
                            if (mid) pendingMessage[userId] = mid;
                        } else {
                            await tgSend(userId, "❌ Anda tidak memiliki akses untuk perintah ini.");
                        }
                        continue;
                    }

                    // --- STATE HANDLERS ---
                    if (waitingAdminInput.has(userId)) {
                        waitingAdminInput.delete(userId);
                        const newRanges = [];
                        const lines = text.trim().split('\n');
                        lines.forEach(line => {
                            if (line.includes(' > ')) {
                                const parts = line.split(' > ');
                                const rangeP = parts[0].trim();
                                const countryN = parts[1].trim().toUpperCase();
                                const serviceN = parts.length > 2 ? parts[2].trim().toUpperCase() : "WA";
                                const emoji = GLOBAL_COUNTRY_EMOJI[countryN] || "🗺️";
                                newRanges.push({ range: rangeP, country: countryN, emoji: emoji, service: serviceN });
                            }
                        });
                        const pMsgId = pendingMessage[userId];
                        delete pendingMessage[userId];
                        if (newRanges.length > 0) {
                            const current = loadInlineRanges();
                            current.push(...newRanges);
                            saveInlineRanges(current);
                            await tgEdit(userId, pMsgId, `✅ Berhasil menyimpan ${newRanges.length} range baru.`);
                        } else {
                            await tgEdit(userId, pMsgId, "❌ Format tidak valid.");
                        }
                        continue;
                    }

                    if (waitingBroadcastInput.has(userId)) {
                        waitingBroadcastInput.delete(userId);
                        const pMsgId = broadcastMessage[userId];
                        delete broadcastMessage[userId];
                        if (text.trim().toLowerCase() === ".batal") {
                            await tgEdit(chatId, pMsgId, "❌ Siaran dibatalkan.");
                        } else {
                            await tgEdit(chatId, pMsgId, "✅ Memulai siaran...");
                            await tgBroadcast(text, userId);
                        }
                        continue;
                    }

                    if (waitingDanaInput.has(userId)) {
                        const lines = text.trim().split('\n');
                        if (lines.length >= 2) {
                            const dNum = lines[0].trim();
                            const dName = lines.slice(1).join(' ').trim();
                            if (/^[\d+]+$/.test(dNum)) {
                                waitingDanaInput.delete(userId);
                                updateUserDana(userId, dNum, dName);
                                await tgSend(userId, `✅ <b>Dana Berhasil Disimpan!</b>\n\nNo: ${dNum}\nA/N: ${dName}`);
                            } else {
                                await tgSend(userId, "❌ Format salah. Pastikan baris pertama adalah NOMOR DANA.");
                            }
                        } else {
                            await tgSend(userId, "❌ Format salah. Mohon kirim:\n\n<code>08123456789\nNama Pemilik</code>");
                        }
                        continue;
                    }

                    // --- MANUAL & GET10 INPUT PROCESS ---
                    if (get10RangeInput.has(userId)) {
                        get10RangeInput.delete(userId);
                        const prefix = text.trim();
                        let menuMsgId = pendingMessage[userId];
                        delete pendingMessage[userId];
                        if (/^\+?\d{3,15}[Xx*#]+$/.test(prefix)) {
                            if (!menuMsgId) menuMsgId = await tgSend(chatId, getProgressMessage(0, 0, prefix, 10));
                            else await tgEdit(chatId, menuMsgId, getProgressMessage(0, 0, prefix, 10));
                            processUserInput(userId, prefix, 10, usernameTg, firstName, menuMsgId);
                        } else {
                            await tgSend(chatId, "❌ Format Range tidak valid.");
                        }
                        continue;
                    }

                    const isManualFormat = /^\+?\d{3,15}[Xx*#]+$/.test(text.trim());
                    if (manualRangeInput.has(userId) || (verifiedUsers.has(userId) && isManualFormat)) {
                        manualRangeInput.delete(userId);
                        const prefix = text.trim();
                        let menuMsgId = pendingMessage[userId];
                        delete pendingMessage[userId];
                         if (isManualFormat) {
                            if (!menuMsgId) menuMsgId = await tgSend(chatId, getProgressMessage(0, 0, prefix, 1));
                            else await tgEdit(chatId, menuMsgId, getProgressMessage(0, 0, prefix, 1));
                            processUserInput(userId, prefix, 1, usernameTg, firstName, menuMsgId);
                        } else {
                            await tgSend(chatId, "❌ Format Range tidak valid.");
                        }
                        continue;
                    }

                    if (text.startsWith("/setdana")) {
                        waitingDanaInput.add(userId);
                        await tgSend(userId, "Silahkan kirim dana dalam format:\n\n<code>08123456789\nNama Pemilik</code>");
                        continue;
                    }

                    // --- START ---
                    if (text === "/start") {
                        if (await isUserInBothGroups(userId)) {
                            verifiedUsers.add(userId);
                            saveUsers(userId);
                            const prof = getUserProfile(userId, firstName);
                            const fullName = usernameTg ? `${firstName} (@${usernameTg})` : firstName;
                            
                            const msgProfile = `✅ <b>Verifikasi Berhasil, ${mention}</b>\n\n` +
                                `👤 <b>Profil Anda :</b>\n` +
                                `🔖 <b>Nama</b> : ${fullName}\n` +
                                `🧾 <b>Dana</b> : ${prof.dana}\n` +
                                `👤 <b>A/N</b> : ${prof.dana_an}\n` +
                                `📊 <b>Total of all OTPs</b> : ${prof.otp_semua}\n` +
                                `📊 <b>daily OTP count</b> : ${prof.otp_hari_ini}\n` +
                                `💰 <b>Balance</b> : $${prof.balance.toFixed(6)}\n`;

                            const kb = {
                                inline_keyboard: [
                                    [{ text: "📲 Get Number", callback_data: "getnum" }, { text: "👨‍💼 Admin", url: "https://t.me/" }],
                                    [{ text: "💸 Withdraw Money", callback_data: "withdraw_menu" }]
                                ]
                            };
                            await tgSend(userId, msgProfile, kb);
                        } else {
                            const kb = {
                                inline_keyboard: [
                                    [{ text: "📌 Gabung Grup 1", url: GROUP_LINK_1 }],
                                    [{ text: "📌 Gabung Grup 2", url: GROUP_LINK_2 }],
                                    [{ text: "✅ Verifikasi Ulang", callback_data: "verify" }]
                                ]
                            };
                            await tgSend(userId, `Halo ${mention} 👋\nHarap gabung kedua grup di bawah untuk verifikasi:`, kb);
                        }
                        continue;
                    }
                }

                // --- CALLBACK QUERY ---
                if (upd.callback_query) {
                    const cq = upd.callback_query;
                    const userId = cq.from.id;
                    const dataCb = cq.data;
                    const chatId = cq.message.chat.id;
                    const menuMsgId = cq.message.message_id;
                    const firstName = cq.from.first_name || "User";
                    const usernameTg = cq.from.username;
                    const mention = usernameTg ? `@${usernameTg}` : `<a href='tg://user?id=${userId}'>${firstName}</a>`;

                    if (dataCb === "verify") {
                        if (!(await isUserInBothGroups(userId))) {
                            const kb = {
                                inline_keyboard: [
                                    [{ text: "📌 Gabung Grup 1", url: GROUP_LINK_1 }],
                                    [{ text: "📌 Gabung Grup 2", url: GROUP_LINK_2 }],
                                    [{ text: "✅ Verifikasi Ulang", callback_data: "verify" }]
                                ]
                            };
                            await tgEdit(chatId, menuMsgId, "❌ Belum gabung kedua grup.", kb);
                        } else {
                            verifiedUsers.add(userId);
                            saveUsers(userId);
                            const prof = getUserProfile(userId, firstName);
                            const fullName = usernameTg ? `${firstName} (@${usernameTg})` : firstName;
                            const msgProfile = `✅ <b>Verifikasi Berhasil, ${mention}</b>\n\n` +
                                `👤 <b>Profil Anda :</b>\n` +
                                `🔖 <b>Nama</b> : ${fullName}\n` +
                                `🧾 <b>Dana</b> : ${prof.dana}\n` +
                                `👤 <b>A/N</b> : ${prof.dana_an}\n` +
                                `📊 <b>Total of all OTPs</b> : ${prof.otp_semua}\n` +
                                `📊 <b>daily OTP count</b> : ${prof.otp_hari_ini}\n` +
                                `💰 <b>Balance</b> : $${prof.balance.toFixed(6)}\n`;
                            const kb = {
                                inline_keyboard: [
                                    [{ text: "📲 Get Number", callback_data: "getnum" }, { text: "👨‍💼 Admin", url: "https://t.me/" }],
                                    [{ text: "💸 Withdraw Money", callback_data: "withdraw_menu" }]
                                ]
                            };
                            await tgEdit(chatId, menuMsgId, msgProfile, kb);
                        }
                        continue;
                    }

                    if (dataCb === "getnum") {
                        if (!verifiedUsers.has(userId)) {
                            await tgEdit(chatId, menuMsgId, "⚠️ Harap verifikasi dulu.");
                            continue;
                        }
                        const ranges = loadInlineRanges();
                        const kb = ranges.length > 0 ? generateInlineKeyboard(ranges) : { inline_keyboard: [[{ text: "✍️ Input Manual Range", callback_data: "manual_range" }]] };
                        await tgEdit(chatId, menuMsgId, "<b>Get Number</b>\n\nSilahkan pilih range atau input manual.", kb);
                        continue;
                    }

                    if (dataCb === "manual_range") {
                        if (!verifiedUsers.has(userId)) continue;
                        manualRangeInput.add(userId);
                        await tgEdit(chatId, menuMsgId, "<b>Input Manual Range</b>\n\nKirim Range anda, contoh: <code>2327600XXX</code>");
                        pendingMessage[userId] = menuMsgId;
                        continue;
                    }

                    if (dataCb.startsWith("select_range:")) {
                        if (!verifiedUsers.has(userId)) continue;
                        const prefix = dataCb.split(":")[1];
                        await tgEdit(chatId, menuMsgId, getProgressMessage(0, 0, prefix, 1));
                        processUserInput(userId, prefix, 1, usernameTg, firstName, menuMsgId);
                        continue;
                    }

                    if (dataCb.startsWith("change_num:")) {
                        if (!verifiedUsers.has(userId)) continue;
                        const parts = dataCb.split(":");
                        const numFetch = parseInt(parts[1]);
                        const prefix = parts[2];
                        await tgDelete(chatId, menuMsgId);
                        processUserInput(userId, prefix, numFetch, usernameTg, firstName);
                        continue;
                    }

                    if (dataCb === "withdraw_menu") {
                        const prof = getUserProfile(userId, firstName);
                        const msgWd = `<b>💸 Withdraw Money</b>\n\nSilahkan Pilih Jumlah Withdraw anda\n🧾 Dana: <code>${prof.dana}</code>\n👤 A/N : <code>${prof.dana_an}</code>\n💰 Balance: $${prof.balance.toFixed(6)}\n\n<i>Minimal Withdraw: $${MIN_WD_AMOUNT.toFixed(6)}</i>`;
                        const kbWd = {
                            inline_keyboard: [
                                [{ text: "$1.000000", callback_data: "wd_req:1.0" }, { text: "$2.000000", callback_data: "wd_req:2.0" }],
                                [{ text: "$3.000000", callback_data: "wd_req:3.0" }, { text: "$5.000000", callback_data: "wd_req:5.0" }],
                                [{ text: "⚙️ Setting Dana / Ganti", callback_data: "set_dana_cb" }],
                                [{ text: "🔙 Kembali", callback_data: "verify" }]
                            ]
                        };
                        await tgEdit(chatId, menuMsgId, msgWd, kbWd);
                        continue;
                    }

                    if (dataCb === "set_dana_cb") {
                        waitingDanaInput.add(userId);
                        await tgEdit(chatId, menuMsgId, "Silahkan kirim dana dalam format:\n\n<code>08123456789\nNama Pemilik</code>");
                        continue;
                    }

                    if (dataCb.startsWith("wd_req:")) {
                        const amount = parseFloat(dataCb.split(":")[1]);
                        const profiles = loadProfiles();
                        const prof = profiles[String(userId)];

                        if (!prof || prof.dana === "Belum Diset") {
                            await tgSend(chatId, "❌ Harap Setting Dana terlebih dahulu!");
                            continue;
                        }
                        if (prof.balance < amount) {
                            await tgSend(chatId, `❌ Saldo tidak cukup! Balance anda: $${prof.balance.toFixed(6)}`);
                            continue;
                        }

                        prof.balance -= amount;
                        saveProfiles(profiles);

                        const msgAdmin = `<b>🔔 User meminta Withdraw</b>\n\n👤 User: ${mention}\n🆔 ID: <code>${userId}</code>\n💵 Jumlah: <b>$${amount.toFixed(6)}</b>\n🧾 Dana: <code>${prof.dana}</code>\n👤 A/N: <code>${prof.dana_an}</code>`;
                        const kbAdmin = {
                            inline_keyboard: [[
                                { text: "✅ Approve", callback_data: `wd_act:apr:${userId}:${amount}` },
                                { text: "❌ Cancel", callback_data: `wd_act:cncl:${userId}:${amount}` }
                            ]]
                        };
                        await tgSend(ADMIN_ID, msgAdmin, kbAdmin);
                        await tgEdit(chatId, menuMsgId, "✅ <b>Permintaan Withdraw Terkirim!</b>\nMenunggu persetujuan Admin..");
                        continue;
                    }

                    if (dataCb.startsWith("wd_act:")) {
                        if (userId !== ADMIN_ID) continue;
                        const parts = dataCb.split(":");
                        const action = parts[1];
                        const targetId = parseInt(parts[2]);
                        const amount = parseFloat(parts[3]);

                        if (action === "apr") {
                            await tgEdit(chatId, menuMsgId, `✅ Withdraw User ${targetId} sebesar $${amount} DISETUJUI.`);
                            const prof = getUserProfile(targetId);
                            await tgSend(targetId, `<b>✅ Selamat Withdraw Anda Sukses!</b>\n\n💵 Penarikan : $${amount.toFixed(6)}\n💰 Saldo saat ini: $${prof.balance.toFixed(6)}`);
                        } else if (action === "cncl") {
                            const profiles = loadProfiles();
                            if (profiles[String(targetId)]) {
                                profiles[String(targetId)].balance += amount;
                                saveProfiles(profiles);
                            }
                            await tgEdit(chatId, menuMsgId, `❌ Withdraw User ${targetId} sebesar $${amount} DIBATALKAN.`);
                            await tgSend(targetId, "❌ Admin membatalkan Withdraw.\nSilahkan chat Admin atau melakukan ulang Withdraw.");
                        }
                        continue;
                    }
                }
            }
        }
        await new Promise(r => setTimeout(r, 50));
    }
}

// --- EXPIRY MONITOR ---
async function expiryMonitorTask() {
    setInterval(async () => {
        try {
            const waitList = loadWaitList();
            const now = Date.now() / 1000;
            const updatedList = [];
            for (const item of waitList) {
                if (now - item.timestamp > 1200) { // 20 Menit
                    const msgId = await tgSend(item.user_id, `⚠️ Nomor <code>${item.number}</code> telah kadaluarsa.`);
                    if (msgId) {
                        setTimeout(() => tgDelete(item.user_id, msgId), 30000);
                    }
                } else {
                    updatedList.push(item);
                }
            }
            saveWaitList(updatedList);
        } catch (e) { /* ignore */ }
    }, 10000);
}

// ==============================================================================
// INITIALIZATION
// ==============================================================================

function initializeFiles() {
    [CACHE_FILE, INLINE_RANGE_FILE, AKSES_GET10_FILE, USER_FILE, WAIT_FILE].forEach(f => {
        if (!fs.existsSync(f)) saveJson(f, []);
    });
    if (!fs.existsSync(PROFILE_FILE)) saveJson(PROFILE_FILE, {});
}

async function main() {
    console.log("[INFO] Starting NodeJS Bot...");
    initializeFiles();
    
    // Subprocess dummy sms.py (menggunakan dummy sms.js jika tidak ada python)
    // Asumsi user punya sms.py yang berjalan
    const smsProcess = fork('./sms.js', [], { silent: true });

    // CRON JOB: Restart Browser jam 7 Pagi WIB (Jakarta)
    // "0 7 * * *" artinya menit 0, jam 7, setiap hari
    cron.schedule('0 7 * * *', async () => {
        console.log("[CRON] Refreshing Browser Session (07:00 WIB)...");
        const release = await playwrightLock.acquire();
        try {
            await initBrowser();
        } catch (e) {
            console.error("[CRON ERROR]", e);
        } finally {
            release();
        }
    }, {
        scheduled: true,
        timezone: "Asia/Jakarta"
    });

    try {
        await initBrowser();
        await Promise.all([
            telegramLoop(),
            expiryMonitorTask()
        ]);
    } catch (e) {
        console.error("[FATAL ERROR]", e);
    } finally {
        smsProcess.kill();
    }
}

// Dummy sms.js creator if needed or just handle error
if (!fs.existsSync('sms.js')) {
    fs.writeFileSync('sms.js', "console.log('SMS Service Mock Started'); setInterval(() => {}, 10000);");
}

main();
