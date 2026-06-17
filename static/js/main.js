<script>
    window.onload = function() {
        document.querySelectorAll('input').forEach(i => {
            if(!['submit', 'button'].includes(i.type)) i.value = '';
        })
    }
</script>