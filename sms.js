const fs = require('fs');
const path = require('path');
const axios = require('axios');
const dotenv = require('dotenv');

// Load Env
dotenv.config();

// ================= Konfigurasi Global =================
const BOT_TOKEN = process.env.BOT_TOKEN;
const ADMIN_ID = process.env.ADMIN_ID || "12345678";
const API = `https://api.telegram.org/bot${BOT_TOKEN}`;

const WAIT_TIMEOUT_SECONDS = parseInt(process.env.WAIT_TIMEOUT_SECONDS || "1800");
const EXTENDED_WAIT_SECONDS = 300;
const OTP_REWARD_PRICE = 0.003500;

const SMC_FILE = "smc.json";
const WAIT_FILE = "wait.json";
const PROFILE_FILE = "profile.json";
const SETTINGS_FILE = "settings.json";
const DONATE_LINK = "https://zurastore.my.id/donate";

// ================= Fungsi Utilitas =================

function escapeHtml(text) {
    if (!text) return "";
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function loadJson(filename, defaultVal = []) {
    if (fs.existsSync(filename)) {
        try {
            const data = fs.readFileSync(filename, 'utf8');
            return JSON.parse(data);
        } catch (e) {
            return defaultVal;
        }
    }
    return defaultVal;
}

function saveJson(filename, data) {
    try {
        fs.writeFileSync(filename, JSON.stringify(data, null, 2));
    } catch (e) {
        console.error(`[ERROR] Gagal menyimpan ${filename}:`, e.message);
    }
}

async function tgApi(method, data) {
    try {
        const response = await axios.post(`${API}/${method}`, data, { timeout: 10000 });
        return response.data;
    } catch (e) {
        return null;
    }
}

function updateProfileOtp(userId) {
    const profiles = loadJson(PROFILE_FILE, {});
    const strId = String(userId);
    const today = new Date().toISOString().split('T')[0];

    if (!profiles[strId]) {
        profiles[strId] = {
            name: "User",
            balance: 0.0,
            otp_semua: 0,
            otp_hari_ini: 0,
            last_active: today
        };
    }

    const p = profiles[strId];
    if (p.last_active !== today) {
        p.otp_hari_ini = 0;
        p.last_active = today;
    }

    const oldBal = p.balance || 0.0;
    p.otp_semua = (p.otp_semua || 0) + 1;
    p.otp_hari_ini = (p.otp_hari_ini || 0) + 1;
    p.balance = oldBal + OTP_REWARD_PRICE;

    saveJson(PROFILE_FILE, profiles);
    return { old: oldBal, new: p.balance };
}

// ================= Logika Utama =================

async function checkAndForward() {
    // Refresh settings setiap loop biar kalau admin ganti via main.js, sms.js langsung tau
    const settings = loadJson(SETTINGS_FILE, { balance_enabled: true });
    
    const waitList = loadJson(WAIT_FILE, []);
    if (waitList.length === 0) return;

    let smsData = loadJson(SMC_FILE, []);
    if (!Array.isArray(smsData)) smsData = [];

    let newWaitList = [];
    const currentTime = Date.now() / 1000;
    let smsChanged = false;
    
    const balanceActive = settings.balance_enabled;

    for (const waitItem of waitList) {
        const waitNum = String(waitItem.number);
        const userId = waitItem.user_id;
        const startTs = waitItem.timestamp || 0;
        const otpRecTime = waitItem.otp_received_time;

        if (otpRecTime) {
            if (currentTime - otpRecTime > EXTENDED_WAIT_SECONDS) continue; 
            newWaitList.push(waitItem);
            continue;
        }

        if (currentTime - startTs > WAIT_TIMEOUT_SECONDS) {
            await tgApi("sendMessage", {
                chat_id: userId,
                text: `⚠️ <b>Waktu Habis</b>\nNomor <code>${waitNum}</code> dihapus.`,
                parse_mode: "HTML"
            });
            continue;
        }

        let targetSmsIndex = -1;
        for (let i = 0; i < smsData.length; i++) {
            const sms = smsData[i];
            const smsNum = String(sms.number || sms.Number || "");
            if (smsNum === waitNum) {
                targetSmsIndex = i;
                break;
            }
        }

        if (targetSmsIndex !== -1) {
            const sms = smsData[targetSmsIndex];
            smsData.splice(targetSmsIndex, 1); 
            smsChanged = true;

            const otp = sms.otp || sms.OTP || "N/A";
            const svc = sms.service || "Unknown";
            const raw = escapeHtml(sms.full_message || sms.FullMessage || "");

            let balTxt = "";
            if (!balanceActive) {
                balTxt = "<b>Not available at this time</b>";
            } else if (svc.toLowerCase().includes("whatsapp")) {
                balTxt = "<i>WhatsApp OTP no balance</i>";
            } else {
                const bal = updateProfileOtp(userId);
                balTxt = `$${bal.old.toFixed(6)} > $${bal.new.toFixed(6)}`;
            }

            const msgBody = `🔔 <b>New Message Detected</b>\n\n` +
                            `☎️ <b>Nomor:</b> <code>${waitNum}</code>\n` +
                            `⚙️ <b>Service:</b> <b>${svc}</b>\n\n` +
                            `💰 <b>Added:</b> ${balTxt}\n\n` +
                            `🗯️ <b>Full Message:</b>\n` +
                            `<blockquote>${raw}</blockquote>\n\n` +
                            `⚡ <b>Tap To Copy OTP</b> ⚡`;

            const kb = {
                inline_keyboard: [[
                    { text: ` ${otp}`, copy_text: { text: otp } },
                    { text: "💸 Donate", url: DONATE_LINK }
                ]]
            };

            await tgApi("sendMessage", {
                chat_id: userId,
                text: msgBody,
                reply_markup: kb,
                parse_mode: "HTML"
            });

            waitItem.otp_received_time = currentTime;
            newWaitList.push(waitItem);
        } else {
            newWaitList.push(waitItem);
        }
    }

    if (smsChanged) saveJson(SMC_FILE, smsData);
    saveJson(WAIT_FILE, newWaitList);
}

// ================= Main Loop =================

async function main() {
    if (fs.existsSync(SMC_FILE)) {
        saveJson(SMC_FILE, []);
    }

    console.log("========================================");
    console.log(`[STARTED] Monitor OTP Aktif (Tanpa Conflict)`);
    console.log("========================================");

    // Loop Utama
    while (true) {
        try {
            await checkAndForward();
        } catch (e) {
            console.error(`[LOOP ERROR]`, e);
        }
        await new Promise(resolve => setTimeout(resolve, 2000));
    }
}

main();
