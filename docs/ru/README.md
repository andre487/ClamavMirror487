# Руководство ClamavMirror487

[README](../../README.md) · [English reference](../en/README.md)

## Первый запуск

Нужны Python 3.12+, uv, OpenSSH и существующий администратор с sudo. Проект использует
тот же процесс управления, что MegaProxyServer: приватный inventory, inventory-path,
plan, apply --verify, verify и локальные хуки. Проверена Ubuntu 24.04 с пакетами
caddy и clamav-cvdupdate. Bootstrap через root отсутствует.

```sh
./clamav-mirror inventory --output /private/path/inventory.yml
# Для DNS: добавьте --dns при создании inventory.
# Замените заглушки и проверьте административный SSH-ключ.
./clamav-mirror plan
./clamav-mirror apply --verify --no-hooks
./clamav-mirror verify
```

Файл не перезаписывается при повторном inventory. Путь сохраняется в inventory-path.
--inventory PATH выбирает другой файл, --limit HOST ограничивает хосты. Apply без
ограничения параллельный. --no-hooks не отключает проверку. Команда update вручную
запускает тот же сериализованный сервис, что и timer.

## Настройки

Группа Ansible — clamav_mirrors. Основные переменные: mirror_domain, mirror_email,
mirror_home, mirror_webroot, mirror_update_interval. Домены должны указывать на сервер,
порты 80/443 должны быть доступны. Caddy выпускает и продлевает Let's Encrypt автоматически.
HTTP продолжает отдавать файлы без редиректа; HTTPS допускает просмотр каталога.
Verify проверяет 206 и 32-байтовый Range на обоих протоколах с проверкой сертификата.

mirror_proxy: {} означает прямую загрузку. Для HTTPS-прокси задайте host (host[:port]),
login и password; пароль храните как inline !vault. В файле конфигурации сервера права
0640 root:clamav-mirror. Пароли и URL с реквизитами скрываются в выводе обновляющего
процесса. Для существующего Vault используйте исходный пароль; для нового создайте
приватный файл пароля одной строкой, chmod 600 и резервную копию отдельно.

```sh
export ANSIBLE_VAULT_PASSWORD_FILE=/private/path/vault-password
./clamav-mirror vault encrypt_string --prompt --name mirror_proxy_password
```

Вставьте зашифрованный результат в inventory и используйте его в mirror_proxy.password.
Реальный inventory хранится вне репозитория; inventory-path/.hooks/.generated/.secrets
игнорируются Git. Не публикуйте реквизиты, traffic capture и пароли Vault.

## DNS и обновления

DNS по умолчанию выключен: mirror_dns.enabled: false. В этом режиме нет обращений
к IAM/metadata/DNS API. Для Yandex Cloud укажите enabled: true, zone_id, record_name
и ttl (обычно 300), как в inventory.dns.example.yml. Виртуальной машине нужен service
account с доступом чтения/обновления записей зоны, например dns.editor на эту зону.
Это отдельная опция от сертификатов Caddy.

После успешного cvdupdate публикуется TXT из dns.txt; IAM-токен берётся из metadata.
Запросы metadata/API идут напрямую с таймаутами, только скачивание баз идёт через
прокси. Неуспешное скачивание не публикует DNS. Ошибка DNS не удаляет скачанные базы,
но завершает сервис ошибкой. Verify сравнивает TXT через API; кеши DNS могут отставать
на TTL. Выключение опции не удаляет ранее опубликованную запись.

Отдельный пользователь clamav-mirror хранит состояние в mirror_home/.cvdupdate.
Первый apply обновляет базы, затем включает systemd timer; cron не используется.
Одновременные запуски исключаются systemd и file lock. По умолчанию интервал 30min.

## Система, хуки и эксплуатация

Устанавливаются только runtime/security-пакеты, Caddy, cvdupdate, синхронизация времени,
fail2ban для SSH, UFW, unattended-upgrades и ограничения journald. Авторебут выключен.
Docker/nginx/Certbot/login notifier не устанавливаются. Администратору выдаётся sudo,
его authorized_keys заменяется указанным ключом; root/password SSH login отключается.
До первого применения убедитесь в работоспособности этого ключа и доступности консоли.

Порядок с --verify: apply → verify → хуки. Без флага проверка пропускается. Фильтры
задач apply не ограничивают последующий verify. Ошибка останавливает следующие шаги,
автоматического отката нет. Резервируйте inventory, Vault-пароль, состояние баз и
хранилище сертификатов. После verify проверьте реальный FreshClam-клиент.

Хуки: исполняемый .hooks/post-config-change, затем файлы .hooks/post-config-change.d/
по именам. Окружение CLAMAVMIRROR_ROOT, CLAMAVMIRROR_EVENT, CLAMAVMIRROR_INVENTORY,
CLAMAVMIRROR_ANSIBLE_INVENTORY; рабочий каталог — репозиторий. Хук получает полный
inventory даже с --limit. По умолчанию интеграционных хуков нет.

```sh
sudo systemctl status caddy clamav-mirror-update.timer
sudo journalctl -u clamav-mirror-update --since '1 hour ago'
./clamav-mirror update --limit example
./clamav-mirror check
./clamav-mirror --inventory inventory.example.yml plan --syntax-check
./clamav-mirror --inventory inventory.dns.example.yml plan --syntax-check
```

Check проверяет updater/DNS, кодирование proxy-реквизитов, CLI и хуки без развёртывания
VM. Для восстановления верните проверенные настройки/данные, повторите apply и verify;
это не заменяет резервные копии и не откатывает все системные изменения.
Продовые роли рассчитаны на наливку с нуля: разовые миграционные скрипты/плейбуки
должны оставаться вне репозитория и Git. Зеркалом управляет один проект.

Полный справочник параметров и команд: [English reference](../en/README.md).
