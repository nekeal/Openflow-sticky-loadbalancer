from entities import Server


def generate_servers(n=2):
    """
    Sequentially generates servers' entities with parameters:
    * ip - 192.168.1.x starting from x=2
    * mac - 00:00:00:00:00:xx starting from xx=2
    * port number on switch starting from x=1
    :param n:
    :return:
    """
    return [Server(f"192.168.0.{i+1}", f"00:00:00:00:00:{hex(i+1)[2:].zfill(2)}", i) for i in range(1, 1+n)]


SERVERS = generate_servers(2)
