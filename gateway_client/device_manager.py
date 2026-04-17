from zk import ZK, const

class BiometricManager:
    def __init__(self, ip='10.190.45.94', port=4370):
        self.ip = ip
        self.port = port

    def connect(self):
        zk = ZK(self.ip, port=self.port, timeout=5, password=0, force_udp=False, ommit_ping=False)
        return zk.connect()

    def fetch_all_users(self):
        conn = None
        try:
            conn = self.connect()
            conn.disable_device()
            users = conn.get_users()
            user_list = []
            for user in users:
                user_list.append({
                    'uid': user.uid,
                    'user_id': user.user_id,
                    'name': user.name,
                    'privilege': user.privilege,
                })
            return user_list
        except Exception as e:
            print(f'Error fetching users: {e}')
            return []
        finally:
            if conn:
                conn.enable_device()
                conn.disconnect()

    def process_command(self, action, user_id, first_name, last_name):
        conn = None
        try:
            conn = self.connect()
            conn.disable_device()
            
            # Action logic based on sync queue
            if action == 'ADD_USER':
                # Generate a temporary numeric uid if necessary, or let the device handle it.
                # ZK requires user_id (string) and name (string)
                full_name = f'{first_name} {last_name}'.strip()
                # PyZK set_user: uid, name, privilege, password, group_id, user_id
                # Usually we search if user exists first to get the UID, otherwise we assign a new UID.
                users = conn.get_users()
                uid = None
                for u in users:
                    if u.user_id == user_id:
                        uid = u.uid
                        break
                
                if uid is None:
                    # Find max uid and add 1
                    uid = max([u.uid for u in users] + [0]) + 1
                    
                conn.set_user(uid=uid, name=full_name, privilege=const.USER_DEFAULT, password='', group_id='', user_id=user_id)
                print(f'Successfully added/updated user: {full_name} ({user_id})')
            
            elif action == 'DELETE_USER':
                users = conn.get_users()
                uid = None
                for u in users:
                    if u.user_id == user_id:
                        uid = u.uid
                        break
                if uid is not None:
                    conn.delete_user(uid=uid)
                    print(f'Successfully deleted user: {user_id}')
                    
        except Exception as e:
            print(f'Error processing command: {e}')
        finally:
            if conn:
                conn.enable_device()
                conn.disconnect()
