# 20260120 - Handover 4 - Synapse CT117, ProxyJump, migrations, port-forwarding


## Port forwarding on UbuntuVM2 (friends access now, edge-proxy later)
> Historical snapshot: superseded by `handovers/USNIVERSE_MASTER_HANDOVER.md`.
> Keep for migration/debug history only. If it conflicts with current docs, the master handover wins.

Goal: friends hit UbuntuVM2, UbuntuVM2 forwards TCP ports to CTs.

Forwarded services:
- Synapse: UbuntuVM2:8008 -> CT117 (192.168.1.117:8008)
- n8n:     UbuntuVM2:5678 -> CT116 (192.168.1.116:5678)

Commands (run on UbuntuVM2):
- Enable IP forwarding:
  sudo sysctl -w net.ipv4.ip_forward=1
  sudo sed -i 's/^#\?net.ipv4.ip_forward=.*/net.ipv4.ip_forward=1/' /etc/sysctl.conf
  sudo sysctl -p

- Add iptables rules:
  sudo iptables -t nat -A PREROUTING -p tcp --dport 8008 -j DNAT --to-destination 192.168.1.117:8008
  sudo iptables -A FORWARD -p tcp -d 192.168.1.117 --dport 8008 -m state --state NEW,ESTABLISHED,RELATED -j ACCEPT

  sudo iptables -t nat -A PREROUTING -p tcp --dport 5678 -j DNAT --to-destination 192.168.1.116:5678
  sudo iptables -A FORWARD -p tcp -d 192.168.1.116 --dport 5678 -m state --state NEW,ESTABLISHED,RELATED -j ACCEPT

  sudo iptables -t nat -C POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null || sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

- Verify:
  sudo iptables -t nat -L PREROUTING -n -v
  sudo iptables -L FORWARD -n -v

- Persist across reboot:
  sudo apt-get install -y iptables-persistent
  sudo netfilter-persistent save
  sudo netfilter-persistent list

Rollback (run on UbuntuVM2):
  sudo iptables -t nat -D PREROUTING -p tcp --dport 8008 -j DNAT --to 192.168.1.117:8008
  sudo iptables -D FORWARD -p tcp -d 192.168.1.117 --dport 8008 -j ACCEPT

  sudo iptables -t nat -D PREROUTING -p tcp --dport 5678 -j DNAT --to 192.168.1.116:5678
  sudo iptables -D FORWARD -p tcp -d 192.168.1.116 --dport 5678 -j ACCEPT

Notes:
- No TLS yet. Edge-proxy (CT110) will replace this later with HTTPS + auth.
- Keep ports minimal while exposed.
